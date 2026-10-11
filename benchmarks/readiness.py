"""Report which level-B gates are open, read from the live constants.

**What this is for.** ``docs/runbook/thu-nghiem-cuc-bo.md`` already describes
the level-B blockers at length, and prose is the thing that goes stale: a
runbook saying "the RAM threshold is pending" stays convincing after somebody
approves one. This module answers the same question by reading the constants
the gates themselves read, so it cannot disagree with them.

**What it is not.** It is not an authorisation. Exit ``0`` would mean every
gate listed here holds an approved value - not that a model run may start.
Several level-B preconditions are not expressible as a constant (which of the
three measurement methods to use, which model to run, whether a supervised run
is permitted at all), and they live in runbook sections 4a-4d. An exit code
cannot carry those, so this module says so in its own output rather than
leaving the reader to infer it.

**What it does, mechanically.** Reads four module attributes and formats them.
No subprocess, no socket, no file written, no environment variable set or
read, no model, no GPU query. Deliberately it does *not* read how much memory
is free: every gate here fails on the **absence of an approved policy**, which
no amount of free memory changes, and printing a memory figure beside a policy
refusal is how an operator comes to believe that closing applications will
help. ``preflight.require_cpu_ram_headroom`` makes the same separation in the
same order, and for the same reason.

Output is unaccented Vietnamese: this reaches a Windows console whose code
page is usually not UTF-8.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from benchmarks import artifacts, preflight

EXIT_ALL_APPROVED = 0
"""Every gate listed here holds an approved value. **Not** a permission to run."""

EXIT_GATE_PENDING = 3
"""At least one gate is open. Shares the number the harnesses exit on a refusal."""

GATE_IDS: tuple[str, ...] = (
    "llm-cpu-ram",
    "asr-cpu-ram",
    "model-digest",
    "egress-isolation",
)
"""The gates this report covers, in the order a reader meets them.

A fixed tuple rather than something derived from the modules, because the four
are heterogeneous - two are ``int | None``, one is a ``bool``, one is a
``dict`` - and a rule general enough to find all four would also find
constants that are not gates. The cost of being explicit is that a fifth gate
could be added without appearing here, so ``tests/test_readiness.py`` holds a
completeness check against this tuple rather than trusting the list.
"""

#: Roles whose digest must be pinned before a model binary is run. The ledger
#: in :mod:`benchmarks.artifacts` is keyed by role, so "is the digest pinned"
#: is a question per role, not one flag.
MODEL_ROLES: tuple[str, ...] = ("llm-model", "asr-model")


@dataclass(frozen=True)
class GateSource:
    """The values the report reads, as data.

    A seam, and the only way to test the approved direction: every gate is
    pending today, so a report built straight from the modules can only ever
    be observed saying "pending" - which is exactly what a hardcoded "pending"
    would also say. Tests drive an all-approved source through the same code
    to tell the two apart.

    Holding the *derived* requirement rather than the margin is deliberate:
    the ASR gate is pending for two independent reasons (no margin approved
    **and** no peak ever measured), and this report has no business
    re-deriving that arithmetic. :mod:`benchmarks.preflight` already did it.
    """

    llm_cpu_ram_required_mib: int | None
    asr_cpu_ram_required_mib: int | None
    pinned_model_digests: Mapping[str, str]
    egress_isolation_attested: bool


def live_source() -> GateSource:
    """Read the constants the gates read.

    Plain attribute access, no ``getattr`` with a default. A default would
    turn a renamed or mistyped constant into a permanent, confident "pending"
    - a refusal-shaped lie, which is worse here than an ``AttributeError``
    that names the attribute that moved.
    """
    return GateSource(
        llm_cpu_ram_required_mib=preflight.REQUIRED_FREE_RAM_CPU_MIB,
        asr_cpu_ram_required_mib=preflight.REQUIRED_FREE_RAM_ASR_CPU_MIB,
        pinned_model_digests=artifacts.PINNED_MODEL_DIGESTS,
        egress_isolation_attested=preflight.EGRESS_ISOLATION_ATTESTED,
    )


@dataclass(frozen=True)
class GateState:
    """One gate, as this report sees it.

    ``state`` and ``unblocked_by`` describe the **shape** of what is missing,
    never a value. For the digest gate that is not cosmetic: a digest is the
    fingerprint of a specific file on the owner's machine, and a report that
    prints it has put that fingerprint into console scrollback and into
    whatever captured it.
    """

    gate_id: str
    title: str
    approved: bool
    state: str
    unblocked_by: str

    def as_dict(self) -> dict[str, object]:
        return {
            "gate_id": self.gate_id,
            "title": self.title,
            "approved": self.approved,
            "state": self.state,
            "unblocked_by": self.unblocked_by,
        }


_OWNER_APPROVES = "chu du an duyet mot nguong, roi ghi vao source"


def level_b_gates(source: GateSource | None = None) -> tuple[GateState, ...]:
    """The four level-B gates, in :data:`GATE_IDS` order."""
    read = live_source() if source is None else source

    unpinned = tuple(
        role for role in MODEL_ROLES if read.pinned_model_digests.get(role) is None
    )

    gates = {
        "llm-cpu-ram": GateState(
            gate_id="llm-cpu-ram",
            title="Nguong RAM host cho mot luot chay LLM tren CPU",
            approved=read.llm_cpu_ram_required_mib is not None,
            state=(
                "co nguong da duyet"
                if read.llm_cpu_ram_required_mib is not None
                else "CHUA co nguong duoc duyet (peak da ghi la phep do n=1, "
                "lay mau 300 ms, nen la chan duoi chu khong phai muc an toan)"
            ),
            unblocked_by=_OWNER_APPROVES,
        ),
        "asr-cpu-ram": GateState(
            gate_id="asr-cpu-ram",
            title="Nguong RAM host cho mot luot chay ASR tren CPU",
            approved=read.asr_cpu_ram_required_mib is not None,
            state=(
                "co nguong da duyet"
                if read.asr_cpu_ram_required_mib is not None
                # Two reasons, and both have to be answered. Said here because
                # an operator who only hears "pending" may offer a margin, and
                # a margin on top of no measurement is a number, not a gate.
                else "CHUA co nguong duoc duyet, VA chua co phep do nao lam can "
                "cu (n=0: khong artifact ASR nao duoi var/bench/)"
            ),
            unblocked_by=(
                "can CA HAI: mot phep do RAM host cho duong ASR, va " + _OWNER_APPROVES
            ),
        ),
        "model-digest": GateState(
            gate_id="model-digest",
            title="Digest model da ghim trong source (S2.1 quyet dinh #1)",
            approved=not unpinned,
            # Role names, never the digest itself.
            state=(
                "moi role da co digest ghim"
                if not unpinned
                else "CHUA ghim digest cho role: " + ", ".join(unpinned)
            ),
            unblocked_by=(
                "chu du an ghim digest dung cua file da staged vao "
                "PINNED_MODEL_DIGESTS; khong co co che override"
            ),
        ),
        "egress-isolation": GateState(
            gate_id="egress-isolation",
            title="Co lap egress tang OS cho binary model native (S2.1 #5)",
            approved=read.egress_isolation_attested,
            state=(
                "da duoc khai bao trong source"
                if read.egress_isolation_attested
                else "CHUA duoc khai bao; binary native khong nam duoi audit "
                "hook cua Python nen bang chung do trong tien trinh Python "
                "khong noi gi ve no"
            ),
            unblocked_by=(
                "chu du an dat co lap egress o tang OS roi khai bao trong "
                "source; khong doc tu env, vi mot bien danh sai se tat no"
            ),
        ),
    }
    return tuple(gates[gate_id] for gate_id in GATE_IDS)


def report(source: GateSource | None = None) -> dict[str, object]:
    """The machine-readable form. Same data as :func:`render`, nothing extra."""
    gates = level_b_gates(source)
    return {
        "level": "B",
        "gates": [gate.as_dict() for gate in gates],
        "pending_gate_ids": [gate.gate_id for gate in gates if not gate.approved],
        "all_listed_gates_approved": all(gate.approved for gate in gates),
        # A field, not a sentence in a docstring, because the shape of this
        # report invites exactly one misreading and a JSON consumer never sees
        # the prose.
        "is_permission_to_run": False,
        "level_a_depends_on_these_gates": False,
    }


def render(source: GateSource | None = None) -> str:
    """Human-readable report. ASCII only."""
    gates = level_b_gates(source)
    pending = [gate for gate in gates if not gate.approved]

    lines = [
        "MeetAI - cac cong cap B, doc tu hang so dang chay trong source",
        "",
        f"Cong con mo: {len(pending)}/{len(gates)}",
        "",
    ]
    for gate in gates:
        mark = "DUYET " if gate.approved else "CHUA  "
        lines.append(f"  [{mark}] {gate.gate_id}: {gate.title}")
        lines.append(f"            trang thai: {gate.state}")
        if not gate.approved:
            lines.append(f"            mo bang    : {gate.unblocked_by}")
        lines.append("")

    lines += [
        "Bao cao nay KHONG phai mot phep chay.",
        "  - Exit 0 chi noi bon cong tren co gia tri da duyet.",
        "  - Con nhung dieu kien cap B khong bieu dien duoc bang mot hang so:",
        "    chon phuong phap do (A/B/C), chon model, va phep chay co giam sat.",
        "    Xem docs/runbook/thu-nghiem-cuc-bo.md muc 4a-4d.",
        "  - Cap A (meetai status / dry-run) KHONG di qua cac cong tren.",
        "",
        "Lenh nay chi doc: khong subprocess, khong mang, khong ghi file,",
        "khong doc bo nho, khong model, khong GPU.",
    ]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    """Print the report. Exit 3 while any listed gate is open.

    The exit code encodes the gate state rather than "the report rendered",
    so this is usable as a precondition check in a script. Today that means it
    exits non-zero, which is the honest answer and fails closed. The output
    carries the limit of what exit ``0`` would mean, because a caller reading
    only ``$?`` will not read a docstring.
    """
    parser = argparse.ArgumentParser(
        prog="python -m benchmarks.readiness",
        description=(
            "Read-only: which level-B gates are open. Reads the live "
            "constants; starts nothing and writes nothing."
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the report as JSON instead of human-readable text",
    )
    args = parser.parse_args(argv)

    findings = report()
    if args.json:
        print(json.dumps(findings, indent=2, ensure_ascii=False))
    else:
        print(render())

    approved = findings["all_listed_gates_approved"]
    return EXIT_ALL_APPROVED if approved is True else EXIT_GATE_PENDING


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
