"""Shared test fixtures.

Isolation is autouse and total. Earlier versions deleted a hand-written list of
``MEETAI_*`` names and were not autouse, so most tests ran against the
developer's real environment and working directory - a local ``.env`` or a
single stray variable would have changed what they asserted. A green run that
depends on the machine it ran on is not evidence.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest

CANARY_SECRET = "SENTINEL-CREDENTIAL-MUST-NEVER-APPEAR-IN-OUTPUT"
"""A recognisable value used to prove a credential cannot reach any output.

Long enough that pydantic's repr truncation cannot hide the whole of it, and
distinctive enough that a substring search is meaningful.
"""


@pytest.fixture(autouse=True)
def isolated_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[None]:
    """Run every test with no MeetAI or prohibited variables, and an empty cwd.

    The working directory matters because ``.env`` is resolved relative to it;
    ``tmp_path`` has no ``.env``, so a test that wants one creates it
    explicitly.

    The prohibited names are cleared through the loader's own predicate rather
    than a second hand-written list. When S2.1 decision #3 widened that family
    from ``OTEL_*`` to the model-resolution and proxy variables, a copied list
    here would have left the suite failing on any machine that happens to set
    ``HTTPS_PROXY`` - which is exactly the machine-dependent green run this
    fixture exists to prevent. One predicate, two callers.
    """
    import os

    from meetai.settings import _is_prohibited_egress_name

    for name in list(os.environ):
        if name.upper().startswith("MEETAI_") or _is_prohibited_egress_name(name):
            monkeypatch.delenv(name, raising=False)
    monkeypatch.chdir(tmp_path)
    yield


#: Identifier shapes that are safe to commit: none of them is personal data,
#: and each one is a *shape* a leak would take rather than a person's name.
GENERIC_IDENTIFIER_MARKERS: tuple[str, ...] = (
    "@gmail",
    "@outlook",
    "http://",
    "https://",
    "c:\\",
    "d:\\",
    "/users/",
)

#: Uncommitted, git-ignored, one lowercase marker per line. Holds the real
#: identifiers - the operator's account name, name forms and email fragments.
LOCAL_IDENTIFIERS = (
    Path(__file__).resolve().parent.parent / "var" / ("personal-identifiers.txt")
)


def personal_identifier_markers() -> tuple[str, ...]:
    """Markers a corpus must not contain: generic shapes, plus local ones.

    Two tiers, because a leak detector cannot publish its own list. The real
    identifiers used to be committed as literal tuples in two test files -
    which meant the control worked, and also meant the repository contained
    the account name and an email fragment it was built to keep out. One of
    those tuples, ``OPERATOR_NAME_FORMS``, was not even read by anything: it
    stored personal data while its own docstring said it did not.

    So the generic shapes stay committed and always run, and the identifiers
    move to a git-ignored file. On the operator's machine both tiers run and
    the control is exactly as strong as before. In a published copy the file
    is absent and only the generic tier runs - which is a real reduction, is
    recorded here rather than hidden, and is the unavoidable shape of the
    problem.
    """
    markers = list(GENERIC_IDENTIFIER_MARKERS)
    if LOCAL_IDENTIFIERS.is_file():
        markers.extend(
            line.strip().lower()
            for line in LOCAL_IDENTIFIERS.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.startswith("#")
        )
    return tuple(markers)


def code_tokens(tree: ast.AST) -> set[str]:
    """Every name a module actually uses, with prose excluded.

    The distinction this project settled on after a substring scan fired - now
    five times - on a document describing what it forbids: **a string that is
    a statement is documentation; a string used as an operand is data.** So a
    bare string expression is skipped, while an imported name, an attribute, a
    called function and a string passed to something are all kept.

    Lives here because the fifth occurrence was a second copy of the same
    scan in a second test file. One helper, every caller.
    """
    prose = {
        id(node.value)
        for node in ast.walk(tree)
        if isinstance(node, ast.Expr)
        and isinstance(node.value, ast.Constant)
        and isinstance(node.value.value, str)
    }
    tokens: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            tokens.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            tokens.add(node.module.split(".")[0])
            tokens.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Attribute):
            tokens.add(node.attr)
        elif isinstance(node, ast.Name):
            tokens.add(node.id)
        elif (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in prose
        ):
            tokens.add(node.value)
    return tokens


@pytest.fixture
def env_file(tmp_path: Path) -> Path:
    """Path where a test may write a ``.env`` for the loader to read."""
    return tmp_path / ".env"
