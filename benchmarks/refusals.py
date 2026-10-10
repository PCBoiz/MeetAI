"""Refusal messages for the benchmark CLIs: a role, never a path.

Why this module exists: every benchmark CLI checked its inputs with
``if not path.is_file(): print(f"khong ton tai: {path}")``, which echoed the
operator's argument verbatim. Measured at ``bb848b8`` with
``--model C:/Users/canary-operator/secret-staging/model.gguf``, six scripts printed the
absolute path **and the username inside it** to stderr. Benchmark stderr is
pasted into reports and research notes, so the staging layout and the account
name travelled with it.

The replacement names the **role** the missing file was going to play. That
is strictly more diagnostic than the old message for the loop-style checks:
``for path in (WHISPER, args.manifest, args.model)`` printed a path but never
said which of the three arguments was at fault, whereas ``artifact-missing:
manifest`` does.

Roles are a closed allowlist rather than free text. A denylist of "sensitive
looking" strings would lose to the first new argument name; an allowlist makes
the only way to leak a value a change that fails
``tests/test_benchmark_refusal_leaks.py``.

This does **not** change the hash policy, ``--no-hash``, where artifacts live,
or anything else S2.1 is waiting on Son for. It changes what a refusal prints.
"""

from __future__ import annotations

# Every role a benchmark CLI can refuse on. ASCII, because this reaches a
# Windows console whose codepage is usually not UTF-8.
ARTIFACT_ROLES: frozenset[str] = frozenset(
    {
        "asr-model",
        "audio-clip",
        "llama-bench-binary",
        "llama-binary",
        "llm-binary",
        "llm-model",
        "manifest",
        "reference-tsv",
        "results-json",
        "whisper-binary",
    }
)

MISSING_ARTIFACT_CODE = "artifact-missing"

ALLOWED_BINARY_NAMES: frozenset[str] = frozenset({"llama-cli.exe", "llama-bench.exe"})
"""Executables the **operator may name** via ``--binary``. Closed, by decision.

Scope, stated because the first version of this docstring said "executables a
harness may spawn" and that is wider than what this set governs. Two surfaces
exist and both are closed, by different mechanisms:

- **This set** is enforced at runtime, on exactly one argument:
  ``bench_llm_policy --binary``. Measured, it is the only operator-supplied
  executable argument in the repository.
- **Binaries named in source** - ``whisper-cli.exe``, ``nvidia-smi``,
  ``tasklist`` - come from module constants, never from an argument. They are
  held to a separate, wider allowlist enforced statically by
  ``tests/test_llm_boundary.py::TestNoScriptLaunchesAServerBinary``.

So ``whisper-cli.exe`` not being a member here does **not** mean it is refused;
it means it is not reachable through this argument.

Decided by the project owner 2026-10-10, after measuring that
``bench_llm_policy --binary`` took a free string resolved through
``shutil.which``, so ``--binary <...>/llama-server.exe`` ran with nothing
refusing it - while five network-listening binaries sit unpacked beside
the CLI ones under ``var/``.

An allowlist rather than a denylist of server-shaped names, for the reason
``AGENTS.md`` gives twice: a denylist loses to the first new name. The cost
is stated rather than hidden - a llama.cpp build that renames its CLI means
editing this set, and that edit is the review.
"""

DISALLOWED_BINARY_CODE = "binary-not-allowlisted"


def disallowed_binary() -> str:
    """Refusal for an executable outside :data:`ALLOWED_BINARY_NAMES`.

    Names the allowlist, never the rejected path: the operator supplied
    that path, and benchmark stderr is quoted into reports.
    """
    allowed = " hoac ".join(sorted(ALLOWED_BINARY_NAMES))
    return f"{DISALLOWED_BINARY_CODE}: chi nhan {allowed} (duong dan khong duoc in)"


def missing_artifact(role: str) -> str:
    """Return the refusal line for a missing input, with no path in it.

    The role must be a member of :data:`ARTIFACT_ROLES`. An unknown role is a
    programming error and raises, rather than being passed through into the
    message - passing it through is exactly how a formatted value would get
    out.
    """
    if role not in ARTIFACT_ROLES:
        raise ValueError(f"unknown artifact role ({len(role)} chars)")
    return f"{MISSING_ARTIFACT_CODE}: {role} (duong dan khong duoc in)"
