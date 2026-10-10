"""Refuse a GPU benchmark run that the measured budget says will not fit.

Built from the recorded artifacts rather than from a model card. Every number
below is traceable to a key in ``var/bench/*.json``; the derivation is in the
docstrings so a later reader can disagree with the arithmetic rather than with
a bare constant.

**What the artifacts actually say.** Four runs of the S2.3 harness, decoding
configuration **identical** across all four (verified by comparing the
``decoding`` block key by key):

====================================  =====  ====  ====  ====  ====
artifact                              cases  fail  idle  peak   rss
====================================  =====  ====  ====  ====  ====
``llm-policy-s23.json``                  43     0   853  3672  2827
``llm-policy-s23-run2.json``             43     0   760  3590  2827
``llm-policy-s23-power.json``            13     2   841  3639  2868
``llm-policy-s23-cfgv2.json``            43     0   752  3563  2822
====================================  =====  ====  ====  ====  ====

So the run that failed was **not** differently configured, and it did not have
the least headroom either - run 1 started with *more* VRAM in use (853 MiB) and
completed 43 cases. **The difference between the failing run and the successful
ones is not in any recorded variable.** That is the honest finding, and it is
why this module refuses on a margin rather than on a predicted total.

The two failures died at 5.7 s and 7.0 s against a normal 10-13 s, so they
failed during model load rather than during generation.

**A gap in the evidence, stated because it bears on the classification.** Those
two cases were labelled OOM because the harness matched an allocation marker in
stderr at the time; ``failure_evidence`` did not exist yet, so the artifact does
not carry the marker. The field exists now, and the next failure will record
what justified its label. Until a failure is captured with it, "OOM" for those
two rests on an observation that was not persisted.

**Why a margin and not a sum.** S2.2 measured the thing that makes summing
unsafe: two lower-bound peaks adding to 3767 MiB inside 5343 MiB available
still OOM'd, because peak sampling at 250 ms misses the transient
``graph_reserve`` allocation. The under-prediction there was at least 1576 MiB.
Nothing in this repository has measured the spike's actual size - it is
measured only by its consequences - so the margin here is a **judgement**
anchored to that one observation, not a safety factor anybody has established.

**Host RAM is gated too, and the two gates are reported separately.** Running
out of host RAM and running out of VRAM are different failures with different
fixes, and conflating them is how a host allocation marker came to be filed as
an OOM. The RAM budget uses a **small additive** headroom rather than the VRAM
multiplier, because the two metrics lean opposite ways: sampled VRAM
understates a transient peak, while Working Set overstates demand for a
memory-mapped model. See :data:`RAM_HEADROOM_MIB`.

**Per-process VRAM is not available.** Under WDDM ``nvidia-smi -q -d PIDS``
reports per-process memory as ``[N/A]``, so every number above is device-total
and the attributable figure is a subtraction. A second process appearing
between the preflight and the run is invisible to this check; that is what the
shared :mod:`benchmarks.gpulock` is for.
"""

from __future__ import annotations

import ctypes
import sys
from dataclasses import dataclass

from benchmarks.measure import nvidia_smi

TOTAL_VRAM_MIB = 6144
"""GTX 1660 Ti, from ``environment.vram_total_mib`` in every artifact."""

OBSERVED_PEAK_DEVICE_MIB = 3672
"""Highest device-total peak recorded: ``llm-policy-s23.json``."""

OBSERVED_IDLE_AT_THAT_PEAK_MIB = 853
"""Idle VRAM before that same run, so the subtraction below is within-run."""

ATTRIBUTABLE_PEAK_MIB = OBSERVED_PEAK_DEVICE_MIB - OBSERVED_IDLE_AT_THAT_PEAK_MIB
"""What the run itself appears to need: 2819 MiB.

A subtraction, not a measurement. Under WDDM there is no per-process VRAM, so
this attributes the whole rise to the benchmark - which is right only if
nothing else grew during the run. Sampled device totals cannot rule that out.
"""

SPIKE_MARGIN = 0.5
"""Headroom multiplier for the allocation peak nobody has measured.

**A judgement, and the one number here that is not read off an artifact.**
Anchored to the S2.2 under-prediction of at least 1576 MiB, and the honest
statement of that anchor is that **the denominator is arguable**. Against the
configuration that produced the shortfall - two co-resident models summing to
3767 MiB - it is 41.8%. Against this module's single-model attributable peak of
2819 MiB it is 55.9%. Those are different configurations, and 0.5 sits between
the two fractions rather than being derived from either.

So this is a chosen number bracketed by two measurements, not a quotient. Said
plainly because the first version of this docstring quoted only the 55.9%
figure, which made the margin look derived from the observation when the
observation does not determine it.

It is deliberately not larger. At 0.5 the requirement is 4228 MiB free, which
every recorded run would have passed (idle 752-853 leaves 5291-5392 MiB) while
a desktop holding ~1.9 GB would be refused. A larger margin would start
refusing the machine's normal state, and a preflight that always refuses
teaches people to pass ``--force``.
"""

REQUIRED_FREE_MIB = int(ATTRIBUTABLE_PEAK_MIB * (1 + SPIKE_MARGIN))
"""4228 MiB. What must be free before a single sequential run starts."""

OBSERVED_PEAK_WORKING_SET_MIB = 2868
"""Highest per-process working set recorded, from ``llm-policy-s23-power.json``.

The four runs recorded 2827, 2827, 2868 and 2822 MiB. This is the largest, and
it is a **per-process** figure - unlike the VRAM numbers, Windows does report
this one per process, so no subtraction is involved.
"""

RAM_HEADROOM_MIB = 512
"""Additive host-RAM headroom, and additive is the whole argument.

**The two gates lean opposite ways, so they must not share a margin.** VRAM is
sampled at 250 ms and therefore **understates** the peak - a measured shortfall
of at least 1576 MiB says so - which is what justifies a multiplicative margin
there. Working Set **overstates** demand for a memory-mapped GGUF, because
file-backed pages are counted in it and are evictable. Multiplying a number
that already overstates is double-counting.

Measured, not argued: the first version of this gate reused ``SPIKE_MARGIN``
and refused this machine at 3873 MiB available against 4302 required, while
the recorded working-set peak was 2868 MiB - the run would have fitted and the
margin alone refused it. That is exactly the outcome this module warns about
two docstrings up: a preflight that always refuses teaches people to pass
``--force``.

512 MiB is a judgement, like the other margin, and a smaller one. It leaves
room for the harness process and the samplers beside the model without
pretending to cover an allocation nobody has observed on the host side.
"""

REQUIRED_FREE_RAM_MIB = OBSERVED_PEAK_WORKING_SET_MIB + RAM_HEADROOM_MIB
"""3380 MiB of available host RAM before a sequential run starts.

The recorded peak plus :data:`RAM_HEADROOM_MIB`. Conservative in one direction
and honest about it: Working Set can exceed the pages actually committed, so
this is an upper bound on demand derived from a metric that overstates it.
"""


OBSERVED_CPU_PEAK_WORKING_SET_MIB = 4438
"""**Measured fact, n=1.** Peak working set of the one recorded CPU run.

From ``var/bench/llamacpp-qwen3-4b-q4km-cpu-20261007-185559.json``
(``device_flag="none"``, ``requested_ngl=0``). Three CPU artifacts exist; the
other two predate the RAM sampler and carry no working-set key at all, and both
ran with ``device_flag=None``, which ``benchmarks/README.md`` records as *not*
CPU-only. So this is one measurement, not four - unlike
:data:`OBSERVED_PEAK_WORKING_SET_MIB`, which is the largest of four GPU runs.

**It is a lower bound.** ``ProcessRamSampler`` polls at 300 ms, so a peak
between samples was never seen. It is simultaneously an over-statement of
*demand*, because Working Set counts file-backed GGUF pages that are evictable.
Both directions are real and they do not predictably cancel, which is the whole
reason the margin below is not something this module may choose.
"""

CPU_RAM_MARGIN_MIB: int | None = None
"""**Policy, and deliberately absent.** Awaiting the project owner.

Asked and answered 2026-10-10: *keep it pending - refuse every CPU run until a
threshold is approved, because a single 300 ms-sampled observation is not
grounds for a safety threshold.* So this is ``None`` on instruction, not by
oversight.

``None`` is **not** a permissive default. It makes
:func:`require_cpu_ram_headroom` refuse outright, before reading any memory at
all - the absence of an approved threshold is a *different refusal* from not
having enough RAM, and the two report differently. That is the project's
``pending_decision`` doctrine applied here: the absence of a capability, not a
configuration of one.

Two candidate values were put to the owner and neither was taken, for reasons
worth keeping: ``+512`` additive would follow :data:`RAM_HEADROOM_MIB`, whose
argument is that Working Set already overstates demand so multiplying
double-counts - but that margin was chosen against a peak with n=4, and this is
n=1. ``x1.5`` would follow :data:`SPIKE_MARGIN`, but this module already
records measuring a multiplicative host-RAM gate refusing a run that would have
fitted, and a preflight that always refuses teaches people to pass ``--force``.
"""

REQUIRED_FREE_RAM_CPU_MIB: int | None = (
    None
    if CPU_RAM_MARGIN_MIB is None
    else OBSERVED_CPU_PEAK_WORKING_SET_MIB + CPU_RAM_MARGIN_MIB
)
"""Available host RAM required before a CPU run, or ``None`` while pending.

Derived, so approving a margin is a one-line change and the derivation stays
visible. Note it would be **larger** than :data:`REQUIRED_FREE_RAM_MIB` under
either candidate: the CPU path moves the model into host RAM, so the gate built
from GPU runs is the wrong gate, not merely a loose one.
"""


OBSERVED_ASR_CPU_PEAK_WORKING_SET_MIB: int | None = None
"""**No measurement exists.** Not n=1 - n=0.

Measured 2026-10-10: ``var/bench/`` holds no ASR artifact at all, and the four
artifacts that do carry ``ram_peak_working_set_mib`` are every one of them
llama.cpp. So nothing is known about the host-RAM cost of
``bench_asr.py --cpu``.

Kept as its own constant rather than borrowing
:data:`OBSERVED_CPU_PEAK_WORKING_SET_MIB`, because 4438 MiB is the working set
of **Qwen3-4B Q4_K_M**. Whisper's models are different files with different
footprints, so reusing that figure would repeat the error this module already
names about the GPU gate: the wrong gate, not a loose one.
"""

ASR_CPU_RAM_MARGIN_MIB: int | None = None
"""**Policy, absent.** Awaiting the project owner, like its LLM counterpart.

Separate from :data:`CPU_RAM_MARGIN_MIB` on purpose. One approval must not
silently open two paths whose evidence is not even comparable - one has a
single sampled observation, this one has none.
"""

REQUIRED_FREE_RAM_ASR_CPU_MIB: int | None = (
    None
    if (ASR_CPU_RAM_MARGIN_MIB is None or OBSERVED_ASR_CPU_PEAK_WORKING_SET_MIB is None)
    else OBSERVED_ASR_CPU_PEAK_WORKING_SET_MIB + ASR_CPU_RAM_MARGIN_MIB
)
"""Available host RAM required before an ASR CPU run, or ``None`` while pending.

``None`` for two independent reasons, and both have to be answered: there is no
observed peak to build on, and no margin has been approved. Adding a
measurement therefore does not look like approval.
"""


EGRESS_ISOLATION_ATTESTED: bool = False
"""Whether OS-level egress isolation is in place for native model binaries.

**S2.1 decision #5, [CHỐT THEO ỦY QUYỀN CỦA SƠN] 2026-10-10: required.**

The measured fact this answers: ``llama-cli.exe`` and ``whisper-cli.exe`` are
native binaries that are **not** under Python's audit hook, so
``sys.addaudithook`` sees nothing they do. The project's evidence that "no
network event occurs" was gathered inside the Python process and therefore
says nothing about what a child binary does. Only a firewall rule or an
isolated run reaches that.

``False`` by construction, and **this module does not configure anything**. It
cannot: applying a firewall rule is a system change, and an attestation that
the operator has made one is a claim only the operator can make. So this is
the same shape as :data:`CPU_RAM_MARGIN_MIB` - the absence of an approved
state refuses, rather than a default that permits.

Why it is not a settings field or an environment variable: an egress control
that can be switched on by the environment is an egress control that a
mistyped variable switches off. Turning this to ``True`` is a source edit, in
a commit, that a reviewer can see.
"""


class PreflightRefused(RuntimeError):
    """Raised instead of starting a run that the budget says will not fit.

    An exception rather than a boolean so a caller cannot accidentally proceed
    on a falsy return, and a distinct type so a harness can report it as a
    refusal rather than as a failure of the thing being measured.
    """


@dataclass(frozen=True, slots=True)
class VramState:
    """Device-total VRAM, as ``nvidia-smi`` reports it.

    No per-process field, because WDDM does not expose one. Naming it that way
    is deliberate: a reader must not take ``used_mib`` for "used by us".
    """

    total_mib: int
    used_mib: int

    @property
    def free_mib(self) -> int:
        return self.total_mib - self.used_mib

    @property
    def fits(self) -> bool:
        return self.free_mib >= REQUIRED_FREE_MIB

    def metadata(self) -> dict[str, object]:
        return {
            "total_mib": self.total_mib,
            "used_mib": self.used_mib,
            "free_mib": self.free_mib,
            "required_free_mib": REQUIRED_FREE_MIB,
            "attributable_peak_mib": ATTRIBUTABLE_PEAK_MIB,
            "spike_margin": SPIKE_MARGIN,
            "fits": self.fits,
            "per_process_vram": "unavailable under WDDM",
            "required_free_ram_mib": REQUIRED_FREE_RAM_MIB,
            "observed_peak_working_set_mib": OBSERVED_PEAK_WORKING_SET_MIB,
            "ram_headroom_mib": RAM_HEADROOM_MIB,
            "ram_headroom_is_additive_not_multiplicative": True,
        }


def read_vram() -> VramState:
    """Current device-total VRAM. Read-only; touches no model."""
    parts = nvidia_smi("memory.total,memory.used")
    if len(parts) != 2:
        raise PreflightRefused(
            f"khong doc duoc VRAM tu nvidia-smi (nhan {len(parts)} truong). "
            "Khong chay khi khong do duoc: fail closed."
        )
    try:
        total, used = (int(part.split()[0]) for part in parts)
    except (ValueError, IndexError) as exc:
        raise PreflightRefused("nvidia-smi tra ve gia tri VRAM khong parse duoc") from exc
    return VramState(total_mib=total, used_mib=used)


class _MemoryStatusEx(ctypes.Structure):
    """``MEMORYSTATUSEX``, for ``GlobalMemoryStatusEx``.

    ctypes rather than a dependency: adding a package to read one number would
    need a license and provenance note under this project's rules, and the
    call is three lines. ``argtypes``/``restype`` are declared, because the
    default ``c_int`` return truncates on 64-bit and that is a trap this
    repository has already been bitten by once in ``gpulock``.
    """

    _fields_ = [
        ("dwLength", ctypes.c_ulong),
        ("dwMemoryLoad", ctypes.c_ulong),
        ("ullTotalPhys", ctypes.c_ulonglong),
        ("ullAvailPhys", ctypes.c_ulonglong),
        ("ullTotalPageFile", ctypes.c_ulonglong),
        ("ullAvailPageFile", ctypes.c_ulonglong),
        ("ullTotalVirtual", ctypes.c_ulonglong),
        ("ullAvailVirtual", ctypes.c_ulonglong),
        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
    ]


def read_available_ram_mib() -> int:
    """Available physical host RAM, in MiB. Refuses rather than guessing.

    Fail-closed on every branch that cannot produce a number, including the
    non-Windows one: this project runs on Windows, and silently skipping the
    check on another platform would make the gate disappear exactly where
    nobody is watching for it.
    """
    if sys.platform != "win32":
        raise PreflightRefused(
            "khong doc duoc RAM kha dung tren platform nay. Khong chay khi "
            "khong do duoc: fail closed."
        )
    status = _MemoryStatusEx()
    status.dwLength = ctypes.sizeof(_MemoryStatusEx)
    kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel32.GlobalMemoryStatusEx.argtypes = [ctypes.POINTER(_MemoryStatusEx)]
    kernel32.GlobalMemoryStatusEx.restype = ctypes.c_int
    if not kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
        raise PreflightRefused(
            f"GlobalMemoryStatusEx that bai (err {ctypes.get_last_error()}). Fail closed."
        )
    return int(status.ullAvailPhys // (1024 * 1024))


def require_ram_headroom(available_mib: int | None = None) -> int:
    """Refuse unless there is host RAM for the recorded working-set peak.

    Separate from :func:`require_headroom` and reported separately, because
    running out of host RAM and running out of VRAM are different failures
    with different fixes - and because a harness that conflated them is how a
    host allocation marker came to be filed as an OOM in the first place.
    """
    observed = read_available_ram_mib() if available_mib is None else available_mib
    if observed < REQUIRED_FREE_RAM_MIB:
        raise PreflightRefused(
            "khong du RAM host cho mot luot chay tuan tu: "
            f"available={observed} MiB < required={REQUIRED_FREE_RAM_MIB} MiB "
            f"(working set da ghi {OBSERVED_PEAK_WORKING_SET_MIB} MiB + "
            f"{RAM_HEADROOM_MIB} MiB headroom). Dong bot process roi chay lai."
        )
    return observed


def require_headroom(state: VramState | None = None) -> VramState:
    """Refuse unless the measured budget fits. Returns the state it checked.

    Fail-closed on every branch, including the one where the measurement
    itself is unavailable: a run that cannot be measured is a run whose
    failure could not be attributed, and this project's own S2.2 report spends
    several pages on why that is expensive.
    """
    observed = read_vram() if state is None else state
    if not observed.fits:
        raise PreflightRefused(
            "khong du VRAM cho mot luot chay tuan tu: "
            f"free={observed.free_mib} MiB < required={REQUIRED_FREE_MIB} MiB "
            f"(peak quy duoc {ATTRIBUTABLE_PEAK_MIB} MiB + margin "
            f"{SPIKE_MARGIN:.0%}). Dong cac process dang giu VRAM roi chay lai; "
            "khong noi long nguong ma khong version hoa."
        )
    return observed


def require_cpu_ram_headroom(available_mib: int | None = None) -> int:
    """Refuse unless an approved CPU threshold exists **and** the RAM is there.

    Two refusals, in this order, because they are different problems with
    different fixes and conflating them is how a run gets retried in a loop:

    1. **No approved threshold.** Refused before any measurement is taken, so
       the message cannot be read as "free up memory and try again". Nothing
       the operator does to this machine changes it.
    2. **Not enough available RAM**, against the approved threshold.

    Needs no GPU and never calls ``nvidia-smi``: :func:`read_available_ram_mib`
    reads host memory through ``GlobalMemoryStatusEx`` and already fails closed
    on every branch that cannot produce a number. That is what makes this
    usable on a host with no GPU at all, which :func:`require_headroom`
    deliberately is not.
    """
    if REQUIRED_FREE_RAM_CPU_MIB is None:
        raise PreflightRefused(
            "chua co nguong RAM duoc duyet cho mot luot chay CPU. "
            f"Peak da ghi {OBSERVED_CPU_PEAK_WORKING_SET_MIB} MiB la mot phep do "
            "n=1, lay mau 300 ms, nen la chan duoi - khong phai mot muc an toan. "
            "Fail closed cho den khi chu du an duyet mot bien. "
            "Day KHONG phai loi thieu RAM: dong bot process se khong doi gi."
        )
    observed = read_available_ram_mib() if available_mib is None else available_mib
    if observed < REQUIRED_FREE_RAM_CPU_MIB:
        raise PreflightRefused(
            "khong du RAM host cho mot luot chay CPU: "
            f"available={observed} MiB < required={REQUIRED_FREE_RAM_CPU_MIB} MiB "
            f"(peak CPU da ghi {OBSERVED_CPU_PEAK_WORKING_SET_MIB} MiB + "
            f"{CPU_RAM_MARGIN_MIB} MiB margin). Dong bot process roi chay lai."
        )
    return observed


def require_asr_cpu_preflight(available_mib: int | None = None) -> int:
    """Refuse an ASR CPU run. Same shape as the LLM gate, weaker evidence.

    Found by auditing after the LLM gate landed: ``bench_asr.py --cpu`` passes
    ``-ng`` to ``whisper-cli``, which is a model run with no GPU, and nothing
    gated it. The owner's decision was to refuse every CPU run until a
    threshold is approved, so this applies that decision to the path rather
    than making a new one - no margin is chosen here.

    It refuses before reading memory, and it says *no measurement exists*
    rather than naming a number, because naming the LLM number here would be
    the mistake this gate exists to avoid.
    """
    if REQUIRED_FREE_RAM_ASR_CPU_MIB is None:
        raise PreflightRefused(
            "chua co nguong RAM duoc duyet cho mot luot chay ASR tren CPU, va "
            "khong co phep do nao de dung lam can cu: var/bench/ khong co "
            "artifact ASR nao. Fail closed cho den khi chu du an duyet mot "
            "nguong. Day KHONG phai loi thieu RAM."
        )
    observed = read_available_ram_mib() if available_mib is None else available_mib
    if observed < REQUIRED_FREE_RAM_ASR_CPU_MIB:
        raise PreflightRefused(
            "khong du RAM host cho mot luot chay ASR tren CPU: "
            f"available={observed} MiB < required={REQUIRED_FREE_RAM_ASR_CPU_MIB} MiB. "
            "Dong bot process roi chay lai."
        )
    return observed


def require_egress_isolation() -> None:
    """Refuse to run a native model binary without OS-level egress isolation.

    S2.1 decision #5. Distinct from every other refusal in this module on
    purpose: the RAM gates are about whether the machine survives the run, and
    this is about whether anything leaves the machine during it. An operator
    told "not enough RAM" would close applications; an operator told this
    needs to go and configure isolation, which is different work.

    Takes no argument and reads no environment. There is nothing to measure -
    the question is whether a human has put a control in place, and the only
    honest answer available in-process is "nobody has said so".
    """
    if not EGRESS_ISOLATION_ATTESTED:
        raise PreflightRefused(
            "chua co co lap egress tang OS cho binary model native. Chinh sach "
            "S2.1 quyet dinh #5: binary native khong nam duoi audit hook cua "
            "Python, nen bang chung 'khong co su kien mang' do trong tien trinh "
            "Python KHONG noi gi ve no. Fail closed cho den khi co lap duoc dat "
            "va duoc khai bao trong source. Day KHONG phai loi RAM hay GPU."
        )


def require_cpu_preflight(available_mib: int | None = None) -> int:
    """The whole preflight for a CPU run: host RAM, and nothing about the GPU.

    A separate entry point rather than a flag on :func:`require_headroom`,
    because a flag would have to be *passed* correctly at every call site,
    while a missing call is visible in the AST. A CPU run must not reach the
    VRAM gate at all: that gate fails closed when the measurement is
    unavailable, so on a GPU-less host it refuses a run that needs no GPU -
    turning "there is no GPU here" into "there is not enough GPU".
    """
    return require_cpu_ram_headroom(available_mib)


def verify_gpu_released(before: VramState, *, tolerance_mib: int = 256) -> bool:
    """Whether VRAM came back after a run, within a tolerance.

    Called **after** a case, especially a failed one. S2.1 left an orphaned
    ``llama-bench`` holding 2.7 GB because a harness returned without waiting,
    and the next run's numbers were contention rather than performance.

    A tolerance is needed because the driver does not return every byte
    immediately and the desktop's own use drifts; 256 MiB is an order of
    magnitude below the ~2.8 GiB a live model holds, so a leaked model cannot
    hide inside it. Device-total again - there is no per-process figure to
    check, which is why this compares against a *before* reading rather than
    asking who holds what.
    """
    return read_vram().used_mib <= before.used_mib + tolerance_mib


__all__ = [
    "ASR_CPU_RAM_MARGIN_MIB",
    "ATTRIBUTABLE_PEAK_MIB",
    "CPU_RAM_MARGIN_MIB",
    "EGRESS_ISOLATION_ATTESTED",
    "OBSERVED_ASR_CPU_PEAK_WORKING_SET_MIB",
    "OBSERVED_CPU_PEAK_WORKING_SET_MIB",
    "OBSERVED_PEAK_DEVICE_MIB",
    "OBSERVED_PEAK_WORKING_SET_MIB",
    "RAM_HEADROOM_MIB",
    "REQUIRED_FREE_MIB",
    "REQUIRED_FREE_RAM_ASR_CPU_MIB",
    "REQUIRED_FREE_RAM_CPU_MIB",
    "REQUIRED_FREE_RAM_MIB",
    "SPIKE_MARGIN",
    "TOTAL_VRAM_MIB",
    "PreflightRefused",
    "VramState",
    "read_available_ram_mib",
    "read_vram",
    "require_asr_cpu_preflight",
    "require_cpu_preflight",
    "require_cpu_ram_headroom",
    "require_egress_isolation",
    "require_headroom",
    "require_ram_headroom",
    "verify_gpu_released",
]
