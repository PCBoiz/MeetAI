"""Where artifacts may be written, and the digest that must be pinned first.

Two S2.1 decisions, both **[CHỐT THEO ỦY QUYỀN CỦA SƠN]** on 2026-10-10. The
owner delegated these five policy choices; the reasoning is recorded in
``docs/research/2026-10-10-offline-fail-closed-model-artifact.md`` section 7.

**#1 - the digest is mandatory, with no override.** ``bench_llm_policy.py`` had
``--no-hash``, and it had been used in 2 of the 7 recorded measurements, each
writing ``"sha256": "skipped"`` into an artifact that otherwise looked
complete. The flag is removed. But removing it only makes the digest
*recorded*; what makes it a **check** is refusing to run unless the digest
matches a value pinned in committed source. :data:`PINNED_MODEL_DIGESTS` is
that ledger, and it is **empty**: the run refuses by the absence of an
approved digest, exactly as ``preflight.CPU_RAM_MARGIN_MIB`` refuses by the
absence of an approved threshold. The policy is settled here; the value stays
the owner's, because pinning a digest means asserting that one specific staged
file is the right one, and no amount of reasoning establishes that.

**#2 - the artifact root is fixed, relative to the project, and git-ignored.**
Not configurable. This inherits the argument already settled for
``state_dir``: the earlier attempt there tried to enumerate bad locations and
failed to stop a network drive or a cloud-synced folder, while *requiring a
relative path inside the project* excludes both without having to recognise
either. The residual is the same one recorded for ``state_dir``: if the
project directory itself sits inside a synced folder, artifacts are synced
too, and no validator here can see that.

This module spawns nothing, reads no environment variable, hashes nothing and
opens no file. It answers two questions and refuses.
"""

from __future__ import annotations

import pathlib

from benchmarks.refusals import ARTIFACT_ROLES

ARTIFACT_ROOT = pathlib.Path("var")
"""The only directory tree benchmark output may be written to.

Relative on purpose, so it is resolved against the working directory the
operator ran from, and so it cannot name a drive at all. ``var/`` is listed in
``.gitignore``; ``tests/test_benchmark_artifacts.py`` asserts the two have not
drifted apart, because an artifact can embed prompts and model output and git
history does not forget.
"""

SHA256_LENGTH = 64

ARTIFACT_PATH_CODES: frozenset[str] = frozenset(
    {
        "artifact-path-empty",
        "artifact-path-absolute",
        "artifact-path-escapes-root",
        "artifact-path-has-drive",
    }
)
"""Closed set, same discipline as ``refusals.ARTIFACT_ROLES``."""


class ArtifactPathRefused(ValueError):
    """A requested output location is outside the fixed root.

    Carries a code and never the path. The refusal reaches stderr and gets
    pasted into notes, and the path is the operator's own argument - which is
    the leak this project already closed once in the benchmark CLIs.
    """

    def __init__(self, code: str) -> None:
        if code not in ARTIFACT_PATH_CODES:
            raise ValueError(f"unknown artifact path code ({len(code)} chars)")
        super().__init__(f"{code}: duong dan khong duoc in")
        self.code = code


class DigestRefused(RuntimeError):
    """The model digest is not one this project has approved."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DigestNotPinned(DigestRefused):
    """Nobody has pinned a digest for this role yet.

    A subclass rather than a separate type, so a caller that wants to treat
    every digest problem alike can, while the two can still be told apart -
    and they must be, because the fixes are different. "No approved value
    exists" is answered by the owner pinning one. "This file is not the
    pinned one" means the artifact changed, and the question is why.
    """

    def __init__(self, role: str) -> None:
        super().__init__(
            "digest-not-pinned",
            f"digest cua artifact '{role}' chua duoc ghim trong source. "
            "Chinh sach S2.1 quyet dinh #1: digest la BAT BUOC, khong co co "
            "override. Mot lan chay bi tu choi cho den khi chu du an ghim gia "
            "tri dung vao PINNED_MODEL_DIGESTS. Day KHONG phai loi doc file.",
        )


PINNED_MODEL_DIGESTS: dict[str, str] = {}
"""Role to approved SHA-256, lowercase hex. **Empty by decision, not by omission.**

Filling an entry is an assertion that a specific staged file is the correct
one. That is a fact about the owner's machine and the owner's download, so it
is theirs to state; this module only enforces that *something* has been
stated. Leaving it empty therefore refuses every run, which is the intended
behaviour while S2.1 is open - and costs nothing today, because every CPU path
already refuses at the RAM gate.
"""


def artifact_path(*parts: str) -> pathlib.Path:
    """Join ``parts`` under :data:`ARTIFACT_ROOT`, or refuse.

    Refuses rather than sanitising. Silently rewriting ``../../x`` into
    something inside the root would mean the operator asked for one location
    and got another, and the next person to read the artifact would have no
    way to tell.
    """
    if not parts or any(not part for part in parts):
        raise ArtifactPathRefused("artifact-path-empty")
    for part in parts:
        candidate = pathlib.PurePath(part)
        # `PureWindowsPath("D:x").drive` is "D:", and a UNC path's drive is
        # the share - either way, naming a drive means leaving the project.
        if pathlib.PureWindowsPath(part).drive or candidate.is_absolute():
            raise ArtifactPathRefused("artifact-path-has-drive")
        if part.startswith(("/", "\\")):
            raise ArtifactPathRefused("artifact-path-absolute")
    joined = ARTIFACT_ROOT.joinpath(*parts)
    if ".." in joined.parts:
        raise ArtifactPathRefused("artifact-path-escapes-root")
    return joined


def require_role_is_pinned(role: str, *, pinned: dict[str, str] | None = None) -> None:
    """Refuse early, before anybody reads gigabytes to compute a digest.

    Separate from :func:`require_pinned_digest` purely so a caller can check
    the cheap precondition first. Hashing a 2.4 GiB model and *then*
    discovering that no digest was ever pinned is the same refusal, arrived at
    after twenty seconds of disk I/O for nothing.
    """
    if role not in ARTIFACT_ROLES:
        raise ValueError(f"unknown artifact role ({len(role)} chars)")
    ledger = PINNED_MODEL_DIGESTS if pinned is None else pinned
    if ledger.get(role) is None:
        raise DigestNotPinned(role)


def require_pinned_digest(
    role: str, digest: str, *, pinned: dict[str, str] | None = None
) -> str:
    """Return ``digest`` if it is the approved one for ``role``, else refuse.

    ``pinned`` is a seam for the tests, which must be able to exercise the
    match and mismatch paths without a committed digest existing. Production
    callers pass nothing and get :data:`PINNED_MODEL_DIGESTS`.
    """
    if role not in ARTIFACT_ROLES:
        raise ValueError(f"unknown artifact role ({len(role)} chars)")
    ledger = PINNED_MODEL_DIGESTS if pinned is None else pinned
    expected = ledger.get(role)
    if expected is None:
        raise DigestNotPinned(role)
    if len(digest) != SHA256_LENGTH or any(
        character not in "0123456789abcdef" for character in digest
    ):
        # Catches the old behaviour returning in a new spelling: the literal
        # "skipped" that two recorded artifacts contain cannot pass as a
        # measurement.
        raise DigestRefused(
            "digest-malformed",
            f"gia tri digest cho '{role}' khong phai mot SHA-256 "
            f"({len(digest)} ky tu, can {SHA256_LENGTH} chu so hex thuong).",
        )
    if digest != expected:
        raise DigestRefused(
            "digest-mismatch",
            f"digest cua artifact '{role}' khong khop gia tri da ghim: "
            f"doc duoc {digest[:12]}..., da ghim {expected[:12]}.... "
            "Artifact da thay doi; tim nguyen nhan truoc khi chay lai.",
        )
    return digest


__all__ = [
    "ARTIFACT_PATH_CODES",
    "ARTIFACT_ROOT",
    "PINNED_MODEL_DIGESTS",
    "SHA256_LENGTH",
    "ArtifactPathRefused",
    "DigestNotPinned",
    "DigestRefused",
    "artifact_path",
    "require_pinned_digest",
    "require_role_is_pinned",
]
