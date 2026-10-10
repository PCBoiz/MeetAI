"""Drive llama.cpp's own llama-bench, with VRAM sampling and an offload assertion. S2.1.

Why the official binary rather than ``llama-cpp-python``: the prebuilt CUDA
wheel cannot run on this CPU. Its ``ggml-cpu.dll`` is compiled with AVX-512
(``llama_print_system_info`` reports ``AVX512 = 1``) and an i7-9750H
(Coffee Lake-H) has no AVX-512, so context construction dies with
``STATUS_ILLEGAL_INSTRUCTION`` (0xc000001d) *after* reporting a successful
25/25-layer GPU offload. The official release ships fourteen ``ggml-cpu-*``
variants and dispatches at run time, picking ``ggml-cpu-haswell.dll`` here.

**The offload assertion is the point of this wrapper.** llama.cpp falls back to
CPU silently when the CUDA backend cannot load, and keeps accepting ``-ngl``.
That happened on the first run of this benchmark: the CUDA DLLs were on ``PATH``
but a dynamically loaded backend does not search ``PATH`` the same way, so
``ggml-cuda.dll`` never loaded, the run reported ``backend = CPU``, and the
numbers would have been filed as GPU results. A benchmark that cannot tell
which device it used is not measuring anything, so this script refuses to
report a GPU run it cannot evidence twice over: the backend string from
llama-bench **and** a non-trivial VRAM rise over the idle baseline.

Usage (from the repository root):

    var/bench-venv/Scripts/python.exe benchmarks/bench_llamacpp.py \
        --model models/llm/Qwen3-4B-Q4_K_M.gguf --ngl 99 -r 5
"""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import json
import pathlib
import platform
import subprocess
import sys
import time

# Two inserts, and both are needed. The first is this directory, for the
# sibling modules below. The second is the repository root, because
# `preflight` imports `benchmarks.measure` by package path - and when this
# file is run as a *script* (which is how `benchmarks/README.md` documents
# it) sys.path[0] is this directory and the root is absent, so the import
# fails. Measured, not assumed.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(1, str(pathlib.Path(__file__).resolve().parent.parent))

from benchmarks.artifacts import artifact_path
from benchmarks.preflight import (
    PreflightRefused,
    require_cpu_preflight,
    require_egress_isolation,
)
from benchmarks.refusals import missing_artifact
from gpulock import GpuBenchmarkBusyError, gpu_benchmark_lock
from measure import Environment, GpuSampler, ProcessRamSampler

BUILD_DIR = pathlib.Path("var/llamacpp/b11464")
"""Pinned build. Recorded in docs/research so a number can be traced to it."""

MIN_VRAM_RISE_MIB = 64
"""Below this the run is not treated as GPU-resident, whatever it claims.

Not a tuning constant: a real offload of any model in this project's size
range moves hundreds of MiB, and desktop jitter on an idle GPU is a few MiB.
The threshold exists to catch "it said CUDA but nothing moved", not to grade
memory use."""


def sha256_of(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=pathlib.Path)
    parser.add_argument("--ngl", type=int, default=99)
    parser.add_argument("-r", "--repetitions", type=int, default=5)
    parser.add_argument("-p", "--prompt-tokens", default="128,512")
    parser.add_argument("-n", "--gen-tokens", default="64")
    parser.add_argument("--label", default="")
    parser.add_argument(
        "--device",
        default="",
        help=(
            "llama.cpp -dev value. Use 'none' for a true CPU-only run: -ngl 0 "
            "is NOT CPU-only, it still registers the CUDA backend and still "
            "allocated 741 MiB of VRAM when measured."
        ),
    )
    parser.add_argument(
        "--expect",
        choices=("gpu", "cpu"),
        default="gpu",
        help="What device this run is supposed to use. A mismatch fails.",
    )
    args = parser.parse_args()

    binary = BUILD_DIR / "llama-bench.exe"
    # A CPU run is gated on host RAM, and that gate currently refuses:
    # the owner decided to keep the threshold pending because the one
    # recorded CPU peak is a single sampled observation. Checked before
    # the artifact checks are even reached, so a refused run never looks
    # at a model path.
    if args.device == "none":
        try:
            require_cpu_preflight()
        except PreflightRefused as exc:
            print(f"preflight tu choi: {exc}", file=sys.stderr)
            return 3

    # The role, not the path: this message is quoted into reports.
    for role, required in (
        ("llm-model", args.model),
        ("llama-bench-binary", binary),
    ):
        if not required.is_file():
            print(missing_artifact(role), file=sys.stderr)
            return 2

    # One lock for every MeetAI GPU benchmark: the GPU is the shared
    # resource, so two different benchmarks overlapping is as damaging
    # as the same one twice.
    # S2.1 decision #5: no native model binary starts without OS-level
    # egress isolation. Placed AFTER the artifact checks and immediately
    # before the native work, which the refusal-leak matrix is what
    # established: putting it first made seven artifact branches
    # unreachable, and those branches are the more diagnostic refusal.
    # The gate only has to precede anything that *runs*; a stat call
    # spawns nothing. Reported separately from the RAM gates - "not
    # enough RAM" sends an operator to close applications, this sends
    # them to configure isolation.
    try:
        require_egress_isolation()
    except PreflightRefused as exc:
        print(f"egress tu choi: {exc}", file=sys.stderr)
        return 4

    try:
        with gpu_benchmark_lock():
            return _locked_main(args, binary)
    except GpuBenchmarkBusyError as busy:
        print(str(busy), file=sys.stderr)
        return 5


def _locked_main(args: argparse.Namespace, binary: pathlib.Path) -> int:
    env = Environment.capture()
    # None, not 0: see Environment.vram_idle_mib_value.
    idle_mib = env.vram_idle_mib_value

    command = [
        str(binary),
        "-m",
        str(args.model),
        "-ngl",
        str(args.ngl),
        "-p",
        args.prompt_tokens,
        "-n",
        args.gen_tokens,
        "-r",
        str(args.repetitions),
        "-o",
        "json",
    ]
    if args.device:
        command += ["-dev", args.device]

    started = time.perf_counter()
    with (
        GpuSampler(interval=0.2) as sampler,
        ProcessRamSampler("llama-bench.exe", interval=0.3) as ram,
    ):
        # `command` is built from an absolute binary path plus this script's
        # own argparse values, passed as a list with no shell.
        completed = subprocess.run(  # noqa: S603
            command, capture_output=True, text=True, timeout=3600, check=False
        )
    wall_s = time.perf_counter() - started

    if completed.returncode != 0:
        print(f"llama-bench exit {completed.returncode}", file=sys.stderr)
        print(completed.stderr[-2000:], file=sys.stderr)
        return 3

    try:
        rows = json.loads(completed.stdout)
    except json.JSONDecodeError:
        print("khong parse duoc json tu llama-bench", file=sys.stderr)
        print(completed.stdout[-1500:], file=sys.stderr)
        return 3

    # `backends` (plural) is the key llama-bench actually emits; reading
    # `backend` returned "?" and the assertion below correctly refused to call
    # a clearly-GPU run a GPU run. Keeping the singular as a fallback in case
    # an older build differs.
    backends = sorted({str(row.get("backends", row.get("backend", "?"))) for row in rows})
    peak = sampler.peak_mib
    rise = (peak - idle_mib) if peak is not None and idle_mib is not None else None

    used_gpu = any("CUDA" in backend for backend in backends) and (
        rise is not None and rise >= MIN_VRAM_RISE_MIB
    )

    record: dict[str, object] = {
        "label": args.label or args.model.stem,
        "llamacpp_build": BUILD_DIR.name,
        "llamacpp_version": rows[0].get("build_commit") if rows else None,
        "model_file": args.model.name,
        "model_sha256": sha256_of(args.model),
        "model_bytes": args.model.stat().st_size,
        "requested_ngl": args.ngl,
        "expected_device": args.expect,
        "backends_reported": backends,
        "cpu_backend_variant": next(
            (
                line.split("from")[-1].strip()
                for line in completed.stderr.splitlines()
                if "loaded CPU backend" in line
            ),
            None,
        ),
        "vram_idle_mib": idle_mib,
        "vram_peak_mib": peak,
        "vram_rise_mib": rise,
        "vram_note": (
            "nvidia-smi sampled every 200 ms. A sampled maximum is a LOWER BOUND "
            "on the true peak, not the peak."
        ),
        "gpu_temp_peak_c": sampler.peak_temp_c,
        "mem_clock_peak_mhz": sampler.peak_mem_clock_mhz,
        "sm_clock_peak_mhz": sampler.peak_sm_clock_mhz,
        "power_peak_w": sampler.peak_power_w,
        "power_note": (
            "enforced.power.limit is 40 W against an 80 W power.max_limit, and "
            "the memory clock stays at 810 MHz of a supported 6001 MHz. Token "
            "generation is memory-bandwidth bound, so these numbers describe "
            "this power profile, not the card's ceiling."
        ),
        "gpu_temp_idle_c": env.gpu_temp_idle_c,
        "ram_peak_working_set_mib": ram.peak_mib,
        "ram_note": (
            "Working Set, sampled every 300 ms. GGUF weights are mmap'd and "
            "file-backed, so Working Set can overstate what must stay resident. "
            "A sampled maximum is a lower bound on the true peak."
        ),
        "device_flag": args.device or "auto",
        "wall_s": round(wall_s, 2),
        "repetitions": args.repetitions,
        "os": f"{platform.system()} {platform.version()}",
        "env": dataclasses.asdict(env),
        "results": [
            {
                "test": f"{row.get('n_prompt')}pp"
                if row.get("n_prompt")
                else f"{row.get('n_gen')}tg",
                "n_prompt": row.get("n_prompt"),
                "n_gen": row.get("n_gen"),
                "backends": row.get("backends", row.get("backend")),
                "gpu_info": row.get("gpu_info"),
                "n_gpu_layers": row.get("n_gpu_layers"),
                "avg_ts": row.get("avg_ts"),
                "stddev_ts": row.get("stddev_ts"),
                "samples_ns": len(row.get("samples_ns") or []),
            }
            for row in rows
        ],
        "device_confirmed_gpu": used_gpu,
    }

    out_dir = artifact_path("bench")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"llamacpp-{record['label']}-{args.expect}-{stamp}.json"
    target.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(record, indent=2, ensure_ascii=False))
    print(f"\nwritten: {target}")

    if args.expect == "gpu" and not used_gpu:
        print(
            "\nFAIL: expected a GPU run. "
            f"backends={backends} vram_rise={rise} MiB (can >= {MIN_VRAM_RISE_MIB}). "
            "Khong bao cao so nay nhu ket qua GPU.",
            file=sys.stderr,
        )
        return 4
    # A CPU run is judged on VRAM, not on the backend string: llama-bench
    # reports `backends: CUDA` whenever the CUDA backend is *registered*, even
    # with `-dev none`, so the string alone would reject every CPU baseline.
    if args.expect == "cpu" and rise is not None and rise >= MIN_VRAM_RISE_MIB:
        print(f"\nFAIL: expected CPU, got {backends}", file=sys.stderr)
        return 4
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
