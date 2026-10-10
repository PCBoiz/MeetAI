"""Measure whether an ASR model and an LLM can be GPU-resident at the same time. S2.2.

This is the first measurement of S2.2 and it is deliberately not "add the two
single measurements". Adding them is the easiest way to conclude the pipeline
fits in 6 GB and be wrong: fragmentation, each process's own CUDA context, and
each model's compute buffers are not captured by either single figure.

**What this can and cannot prove on Windows.** Per-process VRAM is unavailable:
``nvidia-smi --query-compute-apps=used_memory`` returns ``[N/A]`` for every
process under WDDM, so memory cannot be attributed to a process. What *is*
available is the process list itself, so simultaneity is provable even when
attribution is not. Evidence for co-residency is therefore threefold:

1. both processes appear in the compute-app list in the **same sample**,
2. total VRAM while both run is near the sum of the single-run deltas,
3. neither process fails, OOMs, or silently drops to CPU.

Point 3 matters most, because llama.cpp will happily reduce the number of
offloaded layers or fall back to CPU to make something fit, and a run that
quietly moved to the CPU looks like a successful co-residency with bad latency.

Writes JSON to ``var/bench/`` (git-ignored). Prints ASCII only: the project's
terminal output rule, and ASR hypotheses are content-shaped text that has no
business on a console or in a commit.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import json
import pathlib
import re
import subprocess
import sys
import threading
import time

# Two inserts: this directory for the sibling modules, and the repository
# root because `benchmarks.artifacts` is imported by package path and
# sys.path[0] is this directory when the file is run as a script.
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
sys.path.insert(1, str(pathlib.Path(__file__).resolve().parent.parent))

from benchmarks.artifacts import artifact_path
from benchmarks.preflight import PreflightRefused, require_egress_isolation
from gpulock import GpuBenchmarkBusyError, gpu_benchmark_lock
from measure import Environment, nvidia_smi
from refusals import missing_artifact

LLAMA = pathlib.Path("var/llamacpp/b11464/llama-bench.exe")
WHISPER = pathlib.Path("var/whispercpp/b5454/Release/whisper-cli.exe")

MIN_VRAM_RISE_MIB = 64
"""Below this a run is not treated as GPU-resident, whatever it claims."""


def compute_apps() -> list[tuple[str, str]]:
    """(pid, image name) for every process holding a CUDA context.

    ``used_memory`` is deliberately not requested: it is ``[N/A]`` on Windows,
    and asking for a column that is always unavailable invites someone to
    believe a zero.
    """
    executable = __import__("shutil").which("nvidia-smi")
    if executable is None:
        return []
    try:
        out = subprocess.run(  # noqa: S603
            [
                executable,
                "--query-compute-apps=pid,process_name",
                "--format=csv,noheader",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return []
    rows: list[tuple[str, str]] = []
    for line in out.splitlines():
        if "," not in line:
            continue
        pid, _, name = line.partition(",")
        rows.append((pid.strip(), pathlib.Path(name.strip()).name))
    return rows


@dataclasses.dataclass
class Trace:
    """Samples total VRAM and the compute-app set on one background thread.

    One sampler for both processes on purpose. Two independent samplers would
    read the GPU at different instants, and "both resident" is a statement
    about a single instant.
    """

    interval: float = 0.3
    samples: list[dict[str, object]] = dataclasses.field(default_factory=list)
    _stop: threading.Event = dataclasses.field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            parts = nvidia_smi("memory.used,temperature.gpu,clocks.mem,power.draw")
            apps = compute_apps()
            if len(parts) == 4:
                with contextlib.suppress(ValueError):
                    self.samples.append(
                        {
                            "t": round(time.perf_counter(), 3),
                            "vram_mib": int(parts[0]),
                            "temp_c": int(parts[1]),
                            "mem_clock_mhz": int(parts[2]),
                            "power_w": float(parts[3]),
                            "apps": [name for _, name in apps],
                        }
                    )

    def __enter__(self) -> Trace:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def peak_vram(self) -> int | None:
        values = [int(s["vram_mib"]) for s in self.samples]  # type: ignore[call-overload]
        return max(values) if values else None

    def samples_with_both(self, a: str, b: str) -> list[dict[str, object]]:
        """Samples where both image names held a CUDA context at once."""
        found = []
        for sample in self.samples:
            apps = sample.get("apps") or []
            names = list(apps) if isinstance(apps, list) else []
            if any(a in n for n in names) and any(b in n for n in names):
                found.append(sample)
        return found


LLM_BATCH = 2048
"""Logical batch for the LLM. Exposed because it drives the compute-buffer
size, which is what actually ran out of memory: llama.cpp defaults n_batch to
2048 and then reserves prompt-processing buffers to match, so the default is
the least co-resident-friendly setting rather than a neutral one."""


def llm_command(model: pathlib.Path, seconds: int, batch: int = LLM_BATCH) -> list[str]:
    """A llama-bench run long enough to overlap the ASR run.

    Repetitions rather than a sleep, because the model must stay *in use*, not
    merely loaded: an idle process can have its memory paged by the driver,
    and this measurement is about contention as well as capacity.
    """
    return [
        str(LLAMA),
        "-m",
        str(model),
        "-ngl",
        "99",
        "-p",
        "512",
        "-n",
        "64",
        "-r",
        str(max(2, seconds // 12)),
        "-b",
        str(batch),
        "-ub",
        str(min(batch, 512)),
        "-o",
        "json",
    ]


def asr_command(model: pathlib.Path, clip: pathlib.Path) -> list[str]:
    return [
        str(WHISPER),
        "-m",
        str(model),
        "-f",
        str(clip),
        "-l",
        "vi",
        "-nt",
        "-t",
        "4",
    ]


def parse_whisper_timings(stderr: str) -> dict[str, float]:
    out: dict[str, float] = {}
    for key in ("load time", "encode time", "total time"):
        match = re.search(rf"{key}\s*=\s*([0-9.]+) ms", stderr)
        if match:
            out[key.replace(" ", "_")] = float(match.group(1))
    return out


def asr_used_gpu(stderr: str) -> bool:
    return "loaded CUDA backend" in stderr and "use gpu    = 1" in stderr


def run_single(label: str, command: list[str], timeout: int) -> dict[str, object]:
    env = Environment.capture()
    # None, not 0: see Environment.vram_idle_mib_value.
    idle = env.vram_idle_mib_value
    with Trace(interval=0.3) as trace:
        started = time.perf_counter()
        try:
            done = subprocess.run(  # noqa: S603
                command, capture_output=True, text=True, timeout=timeout, check=False
            )
            rc, err = done.returncode, done.stderr
            timed_out = False
        except subprocess.TimeoutExpired:
            rc, err, timed_out = -1, "", True
        wall = time.perf_counter() - started
    peak = trace.peak_vram()
    rise = (peak - idle) if peak is not None and idle is not None else None
    return {
        "label": label,
        "command": [pathlib.Path(command[0]).name, *command[1:]],
        "returncode": rc,
        "timed_out": timed_out,
        "wall_s": round(wall, 2),
        "vram_idle_mib": idle,
        "vram_peak_mib": peak,
        "vram_rise_mib": rise,
        "gpu_resident": bool(rise is not None and rise >= MIN_VRAM_RISE_MIB),
        "whisper_timings_ms": parse_whisper_timings(err),
        "asr_used_gpu": asr_used_gpu(err) if "whisper" in command[0] else None,
        "samples": len(trace.samples),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--llm", required=True, type=pathlib.Path)
    parser.add_argument("--asr", required=True, type=pathlib.Path)
    parser.add_argument("--clip", required=True, type=pathlib.Path)
    parser.add_argument("--overlap-seconds", type=int, default=90)
    parser.add_argument(
        "--llm-batch",
        type=int,
        default=LLM_BATCH,
        help="llama.cpp -b. Drives compute-buffer size and therefore whether "
        "the two models fit together.",
    )
    parser.add_argument("--timeout", type=int, default=1800)
    args = parser.parse_args()

    # The role, not the path: this message is quoted into reports, and the
    # loop never said which of the five was missing anyway.
    for role, path in (
        ("llama-binary", LLAMA),
        ("whisper-binary", WHISPER),
        ("llm-model", args.llm),
        ("asr-model", args.asr),
        ("audio-clip", args.clip),
    ):
        if not path.is_file():
            print(missing_artifact(role), file=sys.stderr)
            return 2

    # One lock for every MeetAI GPU benchmark: the GPU is the shared
    # resource, so two different benchmarks overlapping is as damaging
    # as the same one twice.
    # S2.1 decision #5: no native model binary starts without OS-level
    # egress isolation. Before the lock, not inside it: taking the shared GPU
    # lock only to refuse would block the other benchmarks for no reason.
    # Separate from the RAM gates and reported separately - "not enough RAM"
    # sends an operator to close applications, this one sends them to
    # configure isolation.
    try:
        require_egress_isolation()
    except PreflightRefused as exc:
        print(f"egress tu choi: {exc}", file=sys.stderr)
        return 4

    try:
        with gpu_benchmark_lock():
            return _locked_main(args)
    except GpuBenchmarkBusyError as busy:
        print(str(busy), file=sys.stderr)
        return 5


def _locked_main(args: argparse.Namespace) -> int:
    env = Environment.capture()
    record: dict[str, object] = {
        "env": dataclasses.asdict(env),
        "llm_model": args.llm.name,
        "llm_batch": args.llm_batch,
        "asr_model": args.asr.name,
        "clip": args.clip.name,
        "per_process_vram_available": False,
        "per_process_vram_note": (
            "nvidia-smi --query-compute-apps=used_memory returns [N/A] for every "
            "process under WDDM on Windows, so VRAM cannot be attributed per "
            "process. Simultaneity is evidenced by the process list instead."
        ),
    }

    # --- 1. Each alone, in this session, so the deltas are comparable. ---
    print("[1/3] ASR alone ...")
    record["asr_alone"] = run_single(
        "asr_alone", asr_command(args.asr, args.clip), args.timeout
    )
    print("[2/3] LLM alone ...")
    record["llm_alone"] = run_single(
        "llm_alone", llm_command(args.llm, 40, args.llm_batch), args.timeout
    )

    # --- 2. Both at once. ---
    print("[3/3] both concurrently ...")
    idle = env.vram_idle_mib_value
    with Trace(interval=0.3) as trace:
        started = time.perf_counter()
        llm = subprocess.Popen(  # noqa: S603
            llm_command(args.llm, args.overlap_seconds, args.llm_batch),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        # Wait for the LLM to become GPU-resident before starting the ASR run,
        # otherwise the two never overlap and the test silently measures two
        # sequential runs instead.
        resident_at: float | None = None
        deadline = time.perf_counter() + 120
        while time.perf_counter() < deadline:
            current = nvidia_smi("memory.used")
            if (
                current
                and idle is not None
                and int(current[0]) - idle >= MIN_VRAM_RISE_MIB
            ):
                resident_at = time.perf_counter() - started
                break
            if llm.poll() is not None:
                break
            time.sleep(0.3)

        asr_started = time.perf_counter() - started
        try:
            asr = subprocess.run(  # noqa: S603
                asr_command(args.asr, args.clip),
                capture_output=True,
                text=True,
                timeout=args.timeout,
                check=False,
            )
            asr_rc, asr_err, asr_timeout = asr.returncode, asr.stderr, False
        except subprocess.TimeoutExpired:
            asr_rc, asr_err, asr_timeout = -1, "", True
        asr_finished = time.perf_counter() - started

        # Always reap the child, even when the concurrent run went wrong.
        # Measured consequence of not doing this: a run where the ASR process
        # crashed left llama-bench alive and hung, holding 2.7 GB of working
        # set and its CUDA context. The GPU then refused a 373 MiB allocation
        # and CPU inference failed too, because commit charge was exhausted -
        # which looked for a while like leaked driver state rather than a live
        # process this script forgot to kill.
        try:
            _llm_stdout, llm_err = llm.communicate(timeout=120)
        except subprocess.TimeoutExpired:
            llm.kill()
            _llm_stdout, llm_err = llm.communicate(timeout=60)
            llm_err = (llm_err or "") + chr(10) + "[harness] llm killed"
        wall = time.perf_counter() - started

    # Belt and braces: if anything above left a child behind, say so in the
    # record rather than leaving it for the next run to trip over.
    if llm.poll() is None:
        llm.kill()
        llm.wait(timeout=30)

    both = trace.samples_with_both("whisper-cli", "llama-bench")
    peak = trace.peak_vram()
    record["concurrent"] = {
        "llm_returncode": llm.returncode,
        "asr_returncode": asr_rc,
        "asr_timed_out": asr_timeout,
        "llm_resident_after_s": round(resident_at, 2) if resident_at else None,
        "asr_started_at_s": round(asr_started, 2),
        "asr_finished_at_s": round(asr_finished, 2),
        "wall_s": round(wall, 2),
        "vram_idle_mib": idle,
        "vram_peak_mib": peak,
        "vram_rise_mib": (
            (peak - idle) if peak is not None and idle is not None else None
        ),
        "samples_total": len(trace.samples),
        "samples_with_both_processes": len(both),
        "asr_used_gpu": asr_used_gpu(asr_err),
        "asr_timings_ms": parse_whisper_timings(asr_err),
        # Error text is evidence, not noise. The first concurrent run had both
        # processes exit 0xC0000409 and the record said nothing about why,
        # which made the failure unusable as a finding.
        "asr_stderr_tail": asr_err[-1200:],
        "llm_stderr_tail": llm_err[-1200:],
        "llm_offload_lines": [
            line.strip()[:120]
            for line in llm_err.splitlines()
            if "offload" in line or "CUDA0" in line or "buffer size" in line
        ][:6],
        "peak_temp_c": max(
            (int(s["temp_c"]) for s in trace.samples),  # type: ignore[call-overload]
            default=None,
        ),
        "peak_power_w": max(
            (float(s["power_w"]) for s in trace.samples),  # type: ignore[call-overload]
            default=None,
        ),
    }

    # --- 3. The verdict, with every condition named. ---
    # Plain dict lookups rather than isinstance asserts: mypy does not cover
    # benchmarks/, so the asserts bought no checking and tripped the lint that
    # exists to stop assert being used as a runtime guard.
    alone_asr = dict(record["asr_alone"])  # type: ignore[arg-type]
    alone_llm = dict(record["llm_alone"])  # type: ignore[arg-type]
    conc = dict(record["concurrent"])  # type: ignore[arg-type]

    sum_of_singles = (alone_asr["vram_rise_mib"] or 0) + (alone_llm["vram_rise_mib"] or 0)
    conditions = {
        "both_processes_in_one_sample": len(both) > 0,
        "asr_succeeded": conc["asr_returncode"] == 0 and not conc["asr_timed_out"],
        "llm_succeeded": conc["llm_returncode"] == 0,
        "asr_on_gpu": bool(conc["asr_used_gpu"]),
        "no_vram_shortfall": bool(
            conc["vram_rise_mib"] is not None
            and conc["vram_rise_mib"] >= 0.75 * sum_of_singles
        ),
    }
    record["sum_of_single_rises_mib"] = sum_of_singles
    record["conditions"] = conditions
    record["co_resident"] = all(conditions.values())
    record["verdict_note"] = (
        "co_resident is true only when every condition above holds. It is NOT "
        "inferred from the two single measurements."
    )

    out_dir = artifact_path("bench")
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    target = out_dir / f"coresidency-{stamp}.json"
    target.write_text(json.dumps(record, indent=2, ensure_ascii=True), encoding="utf-8")

    print(json.dumps({k: v for k, v in record.items() if k != "env"}, indent=2))
    print(f"\nwritten: {target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
