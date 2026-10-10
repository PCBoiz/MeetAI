"""Benchmark one GGUF model through llama-cpp-python. S2.1.

Run from the repository root with the benchmark environment:

    var/bench-venv/Scripts/python.exe benchmarks/bench_llm.py \
        --model models/llm/<file>.gguf --gpu-layers -1 --runs 24

Measures load, a cold generation, then warm generations, keeping the three
apart. Peak VRAM is sampled while the work happens and reported against the
idle baseline from the same run, because this GPU drives a desktop and roughly
0.8 GiB is resident before anything loads.

Writes a JSON record per run under ``var/bench/`` (gitignored) and prints a
summary. Nothing here downloads anything: the model path must already exist,
so a benchmark can never quietly fetch weights.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import io
import json
import pathlib
import platform
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
from cuda_preload import preload_cuda
from measure import Environment, GpuSampler, summarise

PROMPTS = (
    "Tom tat ngan gon: nhom da chot hoan thanh phan tich hop vao tuan sau.",
    "Cau hoi: deadline cua phan bao cao la khi nao?",
    "Liet ke ba muc con treo trong cuoc hop.",
    "Giai thich ngan gon vi sao can kiem tra lai so lieu.",
)
"""Unaccented Vietnamese, short, synthetic. Written for this benchmark; no
meeting content. Kept short because this measures throughput and memory, not
summarisation quality - quality is assessed separately."""


def sha256_of(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True, type=pathlib.Path)
    parser.add_argument("--gpu-layers", type=int, default=-1)
    parser.add_argument("--ctx", type=int, default=2048)
    parser.add_argument("--max-tokens", type=int, default=64)
    parser.add_argument("--runs", type=int, default=24)
    parser.add_argument("--label", default="")
    args = parser.parse_args()

    # `--gpu-layers 0` is this harness's CPU request, and it loads the
    # model *in process* - so an un-gated CPU run here is the one that
    # takes the host down, not a child process. Gated first, before any
    # path is examined.
    if args.gpu_layers == 0:
        try:
            require_cpu_preflight()
        except PreflightRefused as exc:
            print(f"preflight tu choi: {exc}", file=sys.stderr)
            return 3

    if not args.model.is_file():
        # The role, not the path: this message is quoted into reports.
        print(missing_artifact("llm-model"), file=sys.stderr)
        return 2

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

    env = Environment.capture()
    loaded = preload_cuda()

    from llama_cpp import Llama

    record: dict[str, object] = {
        "label": args.label or args.model.stem,
        "model_file": args.model.name,
        "model_sha256": sha256_of(args.model),
        "model_bytes": args.model.stat().st_size,
        "gpu_layers": args.gpu_layers,
        "ctx": args.ctx,
        "max_tokens": args.max_tokens,
        "cuda_dlls_preloaded": list(loaded),
        "os": f"{platform.system()} {platform.version()}",
        "python": platform.python_version(),
        "env": dataclasses.asdict(env),
    }

    # Load. Sampled, because a load allocates in bursts and the peak during
    # load can exceed the steady state afterwards.
    stderr_capture = io.StringIO()
    with GpuSampler(interval=0.2) as sampler:
        start = time.perf_counter()
        with contextlib.redirect_stderr(stderr_capture):
            llm = Llama(
                model_path=str(args.model),
                n_gpu_layers=args.gpu_layers,
                n_ctx=args.ctx,
                verbose=True,
                logits_all=False,
            )
        load_s = time.perf_counter() - start
    record["load_s"] = round(load_s, 3)
    record["vram_peak_during_load_mib"] = sampler.peak_mib

    backend_log = stderr_capture.getvalue()
    record["offloaded_to_gpu"] = "CUDA" in backend_log or "offloaded" in backend_log
    for line in backend_log.splitlines():
        if "offloaded" in line or "CUDA_Host" in line or "buffer size" in line:
            record.setdefault("backend_lines", []).append(line.strip()[:160])  # type: ignore[union-attr]

    def generate(prompt: str) -> tuple[float, int]:
        began = time.perf_counter()
        with contextlib.redirect_stderr(io.StringIO()):
            out = llm.create_chat_completion(
                messages=[{"role": "user", "content": prompt}],
                max_tokens=args.max_tokens,
                temperature=0.0,
                seed=7,
            )
        elapsed = time.perf_counter() - began
        tokens = out.get("usage", {}).get("completion_tokens", 0)  # type: ignore[union-attr]
        return elapsed, int(tokens)

    # Cold: the first generation after load. Reported on its own.
    with GpuSampler(interval=0.2) as sampler:
        cold_s, cold_tokens = generate(PROMPTS[0])
    record["cold_s"] = round(cold_s, 3)
    record["cold_tokens"] = cold_tokens
    record["vram_peak_during_cold_mib"] = sampler.peak_mib

    # Warm.
    durations: list[float] = []
    token_counts: list[int] = []
    with GpuSampler(interval=0.2) as sampler:
        for index in range(args.runs):
            elapsed, tokens = generate(PROMPTS[index % len(PROMPTS)])
            durations.append(elapsed)
            token_counts.append(tokens)
    summary = summarise(durations)
    record["warm"] = {
        "samples": summary.samples,
        "p50_s": round(summary.p50_s, 3),
        "p95_s": round(summary.p95_s, 3) if summary.p95_s is not None else None,
        "p95_withheld": summary.withheld_reason,
        "min_s": round(summary.min_s, 3),
        "max_s": round(summary.max_s, 3),
        "mean_s": round(summary.mean_s, 3),
        "total_completion_tokens": sum(token_counts),
        "tokens_per_s_mean": round(sum(token_counts) / sum(durations), 2)
        if sum(durations)
        else None,
    }
    record["vram_peak_during_warm_mib"] = sampler.peak_mib
    record["gpu_temp_peak_c"] = sampler.peak_temp_c
    # None, not 0: an attributable figure without its baseline describes
    # nothing, so it is withheld rather than estimated.
    idle_mib = env.vram_idle_mib_value
    record["vram_idle_baseline_mib"] = idle_mib
    peak = sampler.peak_mib
    if peak is not None and idle_mib is not None:
        record["vram_attributable_mib"] = peak - idle_mib

    out_dir = artifact_path("bench")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"llm-{record['label']}-{stamp}.json"
    target.write_text(json.dumps(record, indent=2, ensure_ascii=False), encoding="utf-8")

    print(json.dumps(record, indent=2, ensure_ascii=False))
    print(f"\nwritten: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
