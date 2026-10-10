"""Measurement helpers for the S2.1 feasibility benchmark.

Deliberately conservative about what a number means, because the easiest way
to finish this slice would be to produce plausible figures that measure
something other than what they are labelled.

Three decisions worth stating:

**VRAM is sampled, not asked for.** ``nvidia-smi`` reports what is resident
now, so a peak has to be caught by polling while work happens; a reading taken
after a run has already missed it. Every figure is reported alongside the
idle baseline measured in the same process, because this GPU has a desktop on
it and roughly 0.8 GiB is in use before anything is loaded. "Peak VRAM" with
no baseline would silently include the window manager.

**Cold and warm runs are never pooled.** The first inference after a load
includes lazy allocation and cache warming, and averaging it with later runs
produces a figure that describes neither.

**A percentile is reported with its sample count or not at all.** A p95 from
20 samples is the second-worst observation; calling it p95 implies a precision
it does not have. :func:`summarise` therefore refuses to emit p95 below a
threshold and says why.
"""

from __future__ import annotations

import shutil
import statistics
import subprocess
import threading
import time
from dataclasses import dataclass, field

MIN_SAMPLES_FOR_P95 = 20
"""Below this, p95 is withheld rather than estimated."""


def _resolve(tool: str) -> str | None:
    """Absolute path of a system tool, or None.

    Resolved rather than invoked by bare name so the executable that runs is
    the one found now, not whatever a later PATH change points at. Returning
    None instead of raising keeps every caller's "measurement unavailable"
    path, which is how a CPU-only machine still produces a usable record.
    """
    return shutil.which(tool)


def nvidia_smi(fields: str) -> list[str]:
    """Query nvidia-smi, returning one string per field. Empty on failure."""
    executable = _resolve("nvidia-smi")
    if executable is None:
        return []
    try:
        # Fixed argument list, no shell, and `fields` is a literal supplied by
        # this module's own callers - never user input.
        out = subprocess.run(  # noqa: S603
            [
                executable,
                f"--query-gpu={fields}",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return []
    return [part.strip() for part in out.split(",")]


@dataclass
class GpuSampler:
    """Polls GPU memory and temperature on a background thread.

    ``interval`` is a trade-off, not a tuning knob: nvidia-smi costs tens of
    milliseconds per call, so polling faster than this starts to perturb the
    thing being measured, while polling slower can miss a short allocation
    spike during model load.
    """

    interval: float = 0.25
    memory_used_mib: list[int] = field(default_factory=list)
    temperature_c: list[int] = field(default_factory=list)
    mem_clock_mhz: list[int] = field(default_factory=list)
    sm_clock_mhz: list[int] = field(default_factory=list)
    power_w: list[float] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            parts = nvidia_smi(
                "memory.used,temperature.gpu,clocks.sm,clocks.mem,power.draw"
            )
            if len(parts) == 5:
                try:
                    self.memory_used_mib.append(int(parts[0]))
                    self.temperature_c.append(int(parts[1]))
                    self.sm_clock_mhz.append(int(parts[2]))
                    self.mem_clock_mhz.append(int(parts[3]))
                    self.power_w.append(float(parts[4]))
                except ValueError:
                    pass

    def __enter__(self) -> GpuSampler:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def peak_mib(self) -> int | None:
        return max(self.memory_used_mib) if self.memory_used_mib else None

    @property
    def peak_temp_c(self) -> int | None:
        return max(self.temperature_c) if self.temperature_c else None

    @property
    def peak_mem_clock_mhz(self) -> int | None:
        return max(self.mem_clock_mhz) if self.mem_clock_mhz else None

    @property
    def peak_sm_clock_mhz(self) -> int | None:
        return max(self.sm_clock_mhz) if self.sm_clock_mhz else None

    @property
    def peak_power_w(self) -> float | None:
        return max(self.power_w) if self.power_w else None


def peak_working_set_mib(image_name: str) -> int | None:
    """Peak working set of any running process with this image name.

    Windows exposes three different numbers - Working Set, Private Bytes and
    Commit - and they are not interchangeable. This reports **Working Set**,
    named explicitly because GGUF weights are memory-mapped and therefore
    file-backed: working set can overstate the pressure that must stay
    resident, while commit understates what is needed for speed. One number
    labelled correctly beats three unlabelled.
    """
    executable = _resolve("tasklist")
    if executable is None:
        return None
    try:
        # Fixed argument list, no shell. `image_name` is a literal passed by
        # the benchmark scripts, not user input.
        out = subprocess.run(  # noqa: S603
            [executable, "/FI", f"IMAGENAME eq {image_name}", "/FO", "CSV", "/NH"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    best: int | None = None
    for line in out.splitlines():
        fields = [f.strip('"') for f in line.split('","')]
        if len(fields) < 5:
            continue
        digits = "".join(ch for ch in fields[4] if ch.isdigit())
        if digits:
            kib = int(digits)
            best = kib if best is None else max(best, kib)
    return None if best is None else best // 1024


@dataclass
class ProcessRamSampler:
    """Polls a child process's working set on a background thread."""

    image_name: str
    interval: float = 0.3
    working_set_mib: list[int] = field(default_factory=list)
    _stop: threading.Event = field(default_factory=threading.Event)
    _thread: threading.Thread | None = None

    def _run(self) -> None:
        while not self._stop.wait(self.interval):
            value = peak_working_set_mib(self.image_name)
            if value is not None:
                self.working_set_mib.append(value)

    def __enter__(self) -> ProcessRamSampler:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        return self

    def __exit__(self, *exc: object) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    @property
    def peak_mib(self) -> int | None:
        return max(self.working_set_mib) if self.working_set_mib else None


@dataclass(frozen=True, slots=True)
class Summary:
    """Latency summary that carries its own sample count.

    ``p95`` is ``None`` when there were too few samples to claim one. A caller
    that wants a number anyway has to look at ``samples`` and decide, which is
    the point.
    """

    samples: int
    p50_s: float
    p95_s: float | None
    min_s: float
    max_s: float
    mean_s: float
    withheld_reason: str | None = None

    def render(self) -> str:
        p95 = (
            f"{self.p95_s:.3f}s"
            if self.p95_s is not None
            else f"n/a ({self.withheld_reason})"
        )
        return (
            f"n={self.samples} p50={self.p50_s:.3f}s p95={p95} "
            f"min={self.min_s:.3f}s max={self.max_s:.3f}s"
        )


def summarise(durations: list[float]) -> Summary:
    """Summarise timings, withholding p95 when the sample is too small."""
    if not durations:
        raise ValueError("khong co mau nao de tong hop")
    ordered = sorted(durations)
    withheld = None
    p95: float | None = None
    if len(ordered) >= MIN_SAMPLES_FOR_P95:
        p95 = statistics.quantiles(ordered, n=20)[18]
    else:
        withheld = f"can >= {MIN_SAMPLES_FOR_P95} mau, co {len(ordered)}"
    return Summary(
        samples=len(ordered),
        p50_s=statistics.median(ordered),
        p95_s=p95,
        min_s=ordered[0],
        max_s=ordered[-1],
        mean_s=statistics.fmean(ordered),
        withheld_reason=withheld,
    )


UNAVAILABLE = "unavailable"
"""Recorded in place of a measurement that could not be taken.

This used to be ``"?"``, and the problem was not the spelling. Every
caller guarded it with ``int(env.vram_idle_mib or 0)``, which reads like
it handles the unavailable case and cannot: ``"?"`` is **truthy**, so
``or 0`` never fires and ``int`` raises ``ValueError``. Measured. It is the
same shape as ``if settings.consent_mode:`` looking like a guard while
failing open - a sentinel that type-checks as the thing it is standing in
for will be used as that thing.

So the string stays a string for the **record** - artifacts are compared by
hand across runs and retyping the recorded fields would break that - and
the *usable* value is reached through :attr:`Environment.vram_idle_mib_value`,
which is ``int | None``. The unavailable state is now a type, not a
spelling.
"""


@dataclass(frozen=True, slots=True)
class Environment:
    """What the machine was when a run happened.

    Recorded per run rather than written once in prose, because a benchmark
    whose environment is described in a paragraph cannot be checked later.
    """

    gpu_name: str
    compute_cap: str
    driver: str
    vram_total_mib: str
    vram_idle_mib: str
    gpu_temp_idle_c: str
    enforced_power_limit_w: str
    max_power_limit_w: str
    mem_clock_max_mhz: str
    sm_clock_max_mhz: str
    captured_at: str
    gpu_probe_ok: bool = True
    """Whether ``nvidia-smi`` answered at all.

    Recorded rather than derived by a reader comparing strings, and it is
    what separates *no GPU on this machine* from *the GPU answered and the
    number was something else*. A CPU-only host is a supported case - see
    :func:`_resolve` - so the absence of a GPU must be a state, not a
    crash."""
    """The power and clock ceiling are recorded because on this machine they,
    not the model, set the generation rate. The GPU is capped at 40 W against
    an 80 W maximum, and under that cap the memory clock sits at 810 MHz of a
    supported 6001 MHz. Token generation is memory-bandwidth bound, so a
    tokens/second figure without this row is uninterpretable: it describes a
    power profile at least as much as it describes the model."""

    @classmethod
    def capture(cls) -> Environment:
        parts = nvidia_smi(
            "name,compute_cap,driver_version,memory.total,memory.used,"
            "temperature.gpu,enforced.power.limit,power.max_limit,"
            "clocks.max.memory,clocks.max.sm"
        )
        probe_ok = len(parts) == 10
        if not probe_ok:
            parts = [UNAVAILABLE] * 10
        return cls(
            gpu_name=parts[0],
            compute_cap=parts[1],
            driver=parts[2],
            vram_total_mib=parts[3],
            vram_idle_mib=parts[4],
            gpu_temp_idle_c=parts[5],
            enforced_power_limit_w=parts[6],
            max_power_limit_w=parts[7],
            mem_clock_max_mhz=parts[8],
            sm_clock_max_mhz=parts[9],
            captured_at=time.strftime("%Y-%m-%d %H:%M:%S"),
            gpu_probe_ok=probe_ok,
        )

    @property
    def vram_idle_mib_value(self) -> int | None:
        """The idle VRAM baseline as a number, or ``None`` if there is none.

        ``None`` is not zero. A zero baseline would make every attributable
        figure equal to the raw peak, which this module's own docstring calls
        out as the way a VRAM number silently comes to include the window
        manager. A caller that cannot get a baseline must report no
        attribution, not a wrong one."""
        if not self.gpu_probe_ok:
            return None
        try:
            return int(self.vram_idle_mib)
        except ValueError:
            return None
