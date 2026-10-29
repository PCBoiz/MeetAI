"""Invariants about the installed environment and the shape of the source.

These are the checks that would otherwise be a sentence in a document nobody
re-reads. They assert properties of the venv and of the code, so that a future
``uv add`` or a convenient shortcut breaks a test instead of a guarantee.
"""

from __future__ import annotations

import ast
import dataclasses
import importlib.metadata
import importlib.util
import pathlib
import re
from pathlib import Path

import pytest

from tests.conftest import code_tokens

SRC = Path(__file__).resolve().parent.parent / "src" / "meetai"


class TestNoTelemetryStack:
    """The real guard against OpenTelemetry egress is the absent SDK.

    Not "no exporter is configured": FastAPI >= 0.142 ships its own telemetry
    subsystem whose ``auto_configure`` defaults to on and whose endpoint comes
    from ``OTEL_EXPORTER_OTLP_ENDPOINT`` in the environment. Configuration
    alone already tries to turn export on; what stops it is that the SDK and
    exporter packages are not installed. So that is what gets asserted.
    """

    @pytest.mark.parametrize(
        "distribution",
        [
            "opentelemetry-sdk",
            "opentelemetry-exporter-otlp",
            "opentelemetry-exporter-otlp-proto-http",
            "opentelemetry-exporter-otlp-proto-grpc",
            "opentelemetry-instrumentation",
        ],
    )
    def test_exporter_distribution_not_installed(self, distribution: str) -> None:
        with pytest.raises(importlib.metadata.PackageNotFoundError):
            importlib.metadata.version(distribution)

    @pytest.mark.parametrize(
        "module",
        ["opentelemetry.sdk", "opentelemetry.exporter", "opentelemetry.instrumentation"],
    )
    def test_exporter_module_not_importable(self, module: str) -> None:
        try:
            spec = importlib.util.find_spec(module)
        except ModuleNotFoundError:
            spec = None
        assert spec is None, f"{module} da co trong moi truong"

    def test_fastapi_version_is_pinned_exactly(self) -> None:
        """An exact pin, so a telemetry-default change cannot arrive silently.

        FastAPI 0.142 ships a first-party telemetry subsystem whose signal
        flags default to on. A `>=` pin cannot hold a review of those
        defaults; with an exact pin, upgrading is a deliberate act and
        `test_ui.py`'s exact-dict assertion fails until any new signal key is
        explicitly disabled.
        """
        assert importlib.metadata.version("fastapi") == "0.142.2"

    def test_opentelemetry_api_is_expected_but_the_sdk_is_not(self) -> None:
        """`opentelemetry-api` cannot be avoided; the SDK is what matters.

        `fastapi` declares `Requires-Dist: opentelemetry-api>=1.44.0`
        unconditionally and imports it at module scope, so `import fastapi`
        imports opentelemetry. That is fine: without the SDK the API's
        providers are no-ops. This test pins the distinction so nobody
        "hardens" the suite by forbidding the api package and breaking the UI.
        """
        importlib.metadata.version("opentelemetry-api")  # must not raise

    @pytest.mark.parametrize(
        "distribution",
        [
            # Three extras pull the SDK, not one: `opentelemetry`, `standard`,
            # `standard-no-fastapi-cloud-cli` and `all` all require it.
            "fastapi-cloud-cli",
            "fastapi-cli",
            "fastar",
            # FastAPI has a dedicated compatibility branch for logfire's
            # meter provider, and logfire ships its own exporter.
            "logfire",
        ],
    )
    def test_no_cloud_or_exporter_sidecar_installed(self, distribution: str) -> None:
        with pytest.raises(importlib.metadata.PackageNotFoundError):
            importlib.metadata.version(distribution)

    def test_fastapi_does_not_require_the_sdk_unconditionally(self) -> None:
        """Catches a future release promoting the SDK to a hard dependency.

        No amount of local configuration could undo that, so it has to be
        caught at the dependency level.
        """
        requires = importlib.metadata.requires("fastapi") or []
        unconditional = [
            spec
            for spec in requires
            if ("opentelemetry-sdk" in spec or "opentelemetry-exporter" in spec)
            and "extra ==" not in spec
        ]
        assert not unconditional, unconditional


class TestNoStrayEnvironmentReads:
    """Every ``MEETAI_*`` variable the codebase reads must be a settings field.

    Otherwise the unknown-name guard turns a legitimate variable into a startup
    failure - and the tempting fix for that is to weaken the guard.
    """

    def test_no_meetai_env_reads_outside_settings(self) -> None:
        pattern = re.compile(r"""(os\.getenv|os\.environ)\s*[(\[]\s*["']MEETAI_""")
        offenders = [
            path.name
            for path in SRC.rglob("*.py")
            if path.name != "settings.py"
            and pattern.search(path.read_text(encoding="utf-8"))
        ]
        assert not offenders, f"doc MEETAI_* ngoai settings.py: {offenders}"

    def test_only_settings_reads_os_environ(self) -> None:
        """Keeps configuration loading in one auditable place."""
        offenders = [
            path.name
            for path in SRC.rglob("*.py")
            if path.name != "settings.py"
            and "os.environ" in path.read_text(encoding="utf-8")
        ]
        assert not offenders, f"truy cap os.environ ngoai settings.py: {offenders}"


class TestDomainIndependence:
    """Policy and content must not depend on a framework.

    The handoff document requires a deterministic policy gate an LLM cannot
    talk past. A gate that imports pydantic can only answer questions about
    pydantic objects, so the import boundary is the design, not a preference.
    """

    @pytest.mark.parametrize(
        "module",
        [
            "policy.py",
            "content.py",
            "errors.py",
            "consent.py",
            "media_gate.py",
            "session.py",
            "authority.py",
            "answerability.py",
            "boundary.py",
            "response.py",
            "adapters/base.py",
            "adapters/fake.py",
        ],
    )
    @pytest.mark.parametrize(
        "forbidden", ["pydantic", "fastapi", "uvicorn", "discord", "sqlalchemy"]
    )
    def test_module_has_no_framework_import(self, module: str, forbidden: str) -> None:
        source = (SRC / module).read_text(encoding="utf-8")
        imports = re.findall(r"^\s*(?:from|import)\s+([\w.]+)", source, re.MULTILINE)
        roots = {name.split(".")[0] for name in imports}
        assert forbidden not in roots, f"{module} import {forbidden}"


class TestNoNetworkCodeYet:
    """Phase 0 opens no socket. A server arrives with slice S0.6.

    The invariant is about *I/O*, not about module names. ``urllib.parse`` is
    a pure string parser and the planner uses it to compare a URL's hostname -
    which is the thing that stops a lookalike domain being accepted, so
    forbidding it would push the code towards substring matching and make it
    less safe. ``urllib.request`` is a different matter and stays forbidden.

    Matching is therefore on the full dotted path rather than the root
    package, so the distinction is expressible.
    """

    FORBIDDEN_MODULES = (
        "socket",
        "ssl",
        "urllib.request",
        "urllib.error",
        "http.client",
        "http.server",
        "requests",
        "httpx",
        "aiohttp",
        "webbrowser",
        "ftplib",
        "smtplib",
    )

    @staticmethod
    def _imported_paths(source: str) -> set[str]:
        """Every dotted module path a file imports."""
        paths: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                paths.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                paths.add(node.module)
                paths.update(f"{node.module}.{alias.name}" for alias in node.names)
        return paths

    @pytest.mark.parametrize("forbidden", FORBIDDEN_MODULES)
    def test_no_network_module_imported(self, forbidden: str) -> None:
        for path in SRC.rglob("*.py"):
            imported = self._imported_paths(path.read_text(encoding="utf-8"))
            assert forbidden not in imported, f"{path.name} import {forbidden}"

    def test_url_parsing_is_the_only_urllib_use(self) -> None:
        """Pin down what the allowance actually permits.

        If a later slice reaches for another urllib submodule, this fails and
        the decision gets made deliberately instead of by precedent.
        """
        used: set[str] = set()
        for path in SRC.rglob("*.py"):
            used.update(
                name
                for name in self._imported_paths(path.read_text(encoding="utf-8"))
                if name.startswith("urllib")
            )
        assert used <= {"urllib.parse", "urllib.parse.urlparse"}, used


class TestNoPersistenceYet:
    """Nothing in ``src/`` writes to disk, and that is a product constraint.

    "Mặc định **không** ghi raw audio / transcript / notes / reply journal bền
    vững" is a decision of the project owner's, not a stage the code happens to
    be at. Today it holds for the strongest possible reason - there is no code
    that could write - and this keeps it that way until somebody changes it on
    purpose.

    **A write appearing here is not automatically a bug.** Persistence is
    expected eventually, gated on 0-U. What must not happen is persistence
    arriving *by accident*, in a slice about something else, with the documents
    still saying nothing is written. So this fails loudly, and the message says
    what to do rather than what went wrong.

    Checked on the AST rather than on text, because the word "write" appears in
    plenty of prose in this source tree and a substring scan would fire on a
    docstring describing the very thing it forbids - which has now happened six
    times in this project.
    """

    PERSISTENCE_MODULES = (
        "sqlite3",
        "pickle",
        "shelve",
        "dbm",
        "marshal",
        "tempfile",
        "shutil",
    )

    #: Methods that put bytes on disk. ``replace`` is deliberately absent: it
    #: collides with ``str.replace``, which is everywhere, and a scan that
    #: cannot tell them apart reports noise instead of writes.
    WRITING_METHODS = (
        "write_text",
        "write_bytes",
        "mkdir",
        "makedirs",
        "touch",
        "unlink",
    )

    WRITING_MODES = ("w", "a", "x", "+")
    OS_MUTATION_METHODS = frozenset(
        {
            "remove",
            "unlink",
            "rename",
            "replace",
            "mkdir",
            "makedirs",
            "rmdir",
            "removedirs",
            "write",
        }
    )
    SHUTIL_MUTATION_METHODS = frozenset(
        {
            "copy",
            "copy2",
            "copyfile",
            "copyfileobj",
            "copymode",
            "copystat",
            "move",
            "rmtree",
        }
    )
    OS_WRITE_FLAGS = frozenset({"O_WRONLY", "O_RDWR", "O_CREAT", "O_TRUNC", "O_APPEND"})

    #: Dotted names that mutate the filesystem, whatever they are spelled
    #: as locally. Built from the two sets above so there is one list to
    #: maintain rather than two that can drift.
    MUTATING_FUNCTIONS = frozenset(
        {f"os.{name}" for name in OS_MUTATION_METHODS}
        | {f"shutil.{name}" for name in SHUTIL_MUTATION_METHODS}
        | {f"pathlib.Path.{name}" for name in WRITING_METHODS}
    )

    @staticmethod
    def _source_files() -> list[Path]:
        return sorted(SRC.rglob("*.py"))

    @classmethod
    def _open_may_write(cls, node: ast.Call, *, bound: bool = False) -> bool:
        """Treat a dynamic explicit mode as a possible write, not as a read."""
        mode_expr: ast.expr | None = None
        if bound and node.args:
            mode_expr = node.args[0]
        elif len(node.args) >= 2:
            mode_expr = node.args[1]
        for keyword in node.keywords:
            if keyword.arg == "mode":
                mode_expr = keyword.value
        if mode_expr is None:
            return False  # Both builtins open() and Path.open() default to read.
        if isinstance(mode_expr, ast.Constant) and isinstance(mode_expr.value, str):
            return any(flag in mode_expr.value for flag in cls.WRITING_MODES)
        return True

    @staticmethod
    def _import_bindings(tree: ast.Module) -> dict[str, str]:
        """Local name to the dotted origin it was imported from.

        Added after a probe found six ways past the previous version, all of
        them the same mistake: the ``os`` and ``shutil`` branches matched on
        the *receiver's spelling*, so ``import os as o`` or
        ``from os import remove`` walked straight through. Resolving the
        file's own import statements first removes the spelling from the
        question - ``o.remove``, ``remove`` and ``os.remove`` all resolve to
        ``os.remove``.
        """
        bindings: dict[str, str] = {}
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    bindings[alias.asname or root] = alias.name if alias.asname else root
            elif isinstance(node, ast.ImportFrom) and node.module:
                for alias in node.names:
                    bindings[alias.asname or alias.name] = f"{node.module}.{alias.name}"
        return bindings

    @classmethod
    def _resolved_target(cls, node: ast.Call, bindings: dict[str, str]) -> str | None:
        """The dotted name a call refers to, as far as imports can tell.

        ``None`` when the receiver is not a plain name - ``Path('x').open``
        and ``self.foo.write_text`` resolve to nothing here, which is why the
        attribute-only checks below still exist and run regardless.
        """
        func = node.func
        if isinstance(func, ast.Name):
            return bindings.get(func.id, func.id)
        if isinstance(func, ast.Attribute) and isinstance(func.value, ast.Name):
            root = bindings.get(func.value.id, func.value.id)
            return f"{root}.{func.attr}"
        return None

    @classmethod
    def _is_write_call(
        cls, node: ast.Call, bindings: dict[str, str] | None = None
    ) -> bool:
        """Recognize common file creation, write, and deletion APIs.

        ``bindings`` defaults to empty so a caller that has no module context
        still gets the attribute-based checks rather than an error; the file
        scan always passes the real bindings.
        """
        resolved = cls._resolved_target(node, bindings or {})
        func = node.func
        if resolved in cls.MUTATING_FUNCTIONS:
            return True
        if resolved == "open":
            # The builtin, or anything bound to the name `open` by an import
            # this file did not make.
            return cls._open_may_write(node)
        if resolved == "io.open":
            return cls._open_may_write(node)
        if resolved == "os.open":
            return cls._os_open_may_write(node)
        if not isinstance(func, ast.Attribute):
            return False
        if func.attr in cls.WRITING_METHODS:
            return True
        if isinstance(func.value, ast.Name) and func.value.id == "os":
            if func.attr in cls.OS_MUTATION_METHODS:
                return True
            if func.attr == "open":
                # Unknown flag expressions fail closed. Literal O_RDONLY (0)
                # is the only allowed os.open form in this static guard.
                if len(node.args) < 2:
                    return True
                flags = node.args[1]
                if isinstance(flags, ast.Constant) and flags.value == 0:
                    return False
                flag_names = {
                    item.attr
                    for item in ast.walk(flags)
                    if isinstance(item, ast.Attribute)
                    and isinstance(item.value, ast.Name)
                    and item.value.id == "os"
                }
                return not flag_names or bool(flag_names & cls.OS_WRITE_FLAGS)
        if func.attr == "open":
            bound = not (isinstance(func.value, ast.Name) and func.value.id == "io")
            return cls._open_may_write(node, bound=bound)
        if isinstance(func.value, ast.Name) and func.value.id == "shutil":
            return func.attr in cls.SHUTIL_MUTATION_METHODS
        return False

    @classmethod
    def _os_open_may_write(cls, node: ast.Call) -> bool:
        """``os.open`` with any flag that is not plainly read-only.

        Unknown flag expressions fail closed. Literal ``O_RDONLY`` (0) is the
        only form this static guard accepts as a read.

        Flags are recognised by the ``O_`` naming convention rather than by the
        receiver being spelled ``os``, so ``o.O_CREAT`` reads the same as
        ``os.O_CREAT``. Anything with no ``O_`` name in it at all is treated as
        unknown and therefore as a write - extracting this method initially
        dropped that fallback, which would have let
        ``os.open(path, some.OTHER)`` pass as a read.
        """
        if len(node.args) < 2:
            return True
        flags = node.args[1]
        if isinstance(flags, ast.Constant) and flags.value == 0:
            return False
        flag_names = {
            item.attr
            for item in ast.walk(flags)
            if isinstance(item, ast.Attribute) and item.attr.startswith("O_")
        }
        return not flag_names or bool(flag_names & cls.OS_WRITE_FLAGS)

    @pytest.mark.parametrize("forbidden", PERSISTENCE_MODULES)
    def test_no_persistence_module_is_imported(self, forbidden: str) -> None:
        for path in self._source_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                # Narrowed with `continue` rather than a default, so `lineno`
                # is only read off a node type that has one. `ast.walk` yields
                # bare `ast.AST`, and reading a statement attribute off that is
                # the kind of thing mypy is here to stop.
                if isinstance(node, ast.Import):
                    roots = [alias.name.split(".")[0] for alias in node.names]
                elif isinstance(node, ast.ImportFrom) and node.module:
                    roots = [node.module.split(".")[0]]
                else:
                    continue
                assert forbidden not in roots, (
                    f"{path.name}:{node.lineno} imports {forbidden}. Persistence is "
                    "gated on 0-U; if this is deliberate, say so in PROJECT_STATE "
                    "and give it tests of its own before relaxing this one."
                )

    def test_nothing_writes_a_file(self) -> None:
        writes = []
        for path in self._source_files():
            tree = ast.parse(path.read_text(encoding="utf-8"))
            bindings = self._import_bindings(tree)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and self._is_write_call(node, bindings):
                    writes.append(f"{path.name}:{node.lineno} {ast.unparse(node.func)}()")
        assert writes == [], (
            f"src/ now writes to disk: {writes}. That may be correct - persistence "
            "is expected once 0-U closes - but it must be deliberate: record it in "
            "PROJECT_STATE, and add tests for retention and deletion before this "
            "list is allowed to grow."
        )

    def test_the_scan_would_catch_a_write(self) -> None:
        """Control, in both directions.

        A scan over files containing none of what it looks for passes for free.
        This runs the same matching over a source that does contain writes, and
        over one that only talks about them.
        """
        writing = ast.parse(
            "import pathlib\n"
            "import os\n"
            "import shutil\n"
            "import io\n"
            "pathlib.Path('x').write_text('y')\n"
            "pathlib.Path('x').open('w')\n"
            "pathlib.Path('x').open(mode=mode)\n"
            "open('x', 'w')\n"
            "open('x', mode='a')\n"
            "open('x', mode=mode)\n"
            "os.open('x', os.O_CREAT | os.O_WRONLY)\n"
            "os.unlink('x')\n"
            "os.write(fd, data)\n"
            "pathlib.Path('x').unlink()\n"
            "shutil.copyfile('a', 'b')\n"
            "io.open('x', 'w')\n"
        )
        found = [
            ast.unparse(node.func)
            for node in ast.walk(writing)
            if isinstance(node, ast.Call)
            and self._is_write_call(node, self._import_bindings(writing))
        ]
        assert sorted(found) == [
            "io.open",
            "open",
            "open",
            "open",
            "os.open",
            "os.unlink",
            "os.write",
            "pathlib.Path('x').open",
            "pathlib.Path('x').open",
            "pathlib.Path('x').unlink",
            "pathlib.Path('x').write_text",
            "shutil.copyfile",
        ]

    def test_an_import_alias_does_not_hide_a_write(self) -> None:
        """The six forms a probe walked straight through before this slice.

        Each one is an ordinary way to spell a write, and each defeated the
        earlier version for the same reason: it matched on how the receiver was
        spelled in the file rather than on what the name was bound to. They are
        listed individually so a future change that re-breaks one of them says
        which.
        """
        aliased = {
            "from-import os": "from os import remove\nremove('x')\n",
            "from-import shutil": "from shutil import rmtree\nrmtree('x')\n",
            "from-import makedirs": "from os import makedirs\nmakedirs('x')\n",
            "module alias os": "import os as o\no.remove('x')\n",
            "module alias shutil": "import shutil as sh\nsh.move('a', 'b')\n",
            "aliased os.replace": "import os as o\no.replace('a', 'b')\n",
            "renamed from-import": "from os import remove as rm\nrm('x')\n",
            "aliased os.open with flags": "import os as o\no.open('x', o.O_CREAT)\n",
            "os.open with an unknown flag": "import os\nos.open('x', some.OTHER)\n",
        }
        missed = []
        for label, snippet in aliased.items():
            tree = ast.parse(snippet)
            bindings = self._import_bindings(tree)
            if not any(
                isinstance(node, ast.Call) and self._is_write_call(node, bindings)
                for node in ast.walk(tree)
            ):
                missed.append(label)
        assert missed == [], f"an alias hid a write: {missed}"

    def test_reading_and_unrelated_calls_stay_quiet(self) -> None:
        """The other half of a guard: it must not fire on everything.

        Without this, widening the guard until it catches every write would be
        trivially achievable by returning True, and the suite would agree.
        """
        quiet = {
            "builtin open for reading": "open('x')\n",
            "Path.open default mode": "import pathlib\npathlib.Path('x').open()\n",
            "Path.read_text": "import pathlib\npathlib.Path('x').read_text()\n",
            "str.replace": "'a'.replace('b', 'c')\n",
            "os.path.join": "import os\nos.path.join('a', 'b')\n",
            "os.open read-only": "import os\nos.open('x', 0)\n",
            "os.open O_RDONLY by name": "import os\nos.open('x', os.O_RDONLY)\n",
            "dataclasses.replace": (
                "import dataclasses\ndataclasses.replace(thing, field=1)\n"
            ),
        }
        noisy = []
        for label, snippet in quiet.items():
            tree = ast.parse(snippet)
            bindings = self._import_bindings(tree)
            if any(
                isinstance(node, ast.Call) and self._is_write_call(node, bindings)
                for node in ast.walk(tree)
            ):
                noisy.append(label)
        assert noisy == [], f"the guard fired on a read or an unrelated call: {noisy}"
        prose_only = ast.parse('"""This module must never write_text anything."""\n')
        assert [n for n in ast.walk(prose_only) if isinstance(n, ast.Call)] == []


class TestTheMediaGateHasNoCallerYet:
    """``require_media_processing_allowed`` is defined, and called by nothing.

    Measured, and worth stating plainly because it is easy to read the wrong
    way round: the function exists, it refuses at defaults, and it has tests -
    yet it is **not currently refusing anything**, because no code path reaches
    it. It is an obligation placed on future media code, not an active control.
    A reader who sees "the media gate has tests" and concludes "the media gate
    is blocking something" has drawn the wrong conclusion, and this ledger
    exists so that conclusion cannot be drawn from the documents either.

    **A caller appearing is the opposite of a defect.** It is the point of the
    function. What this guards against is a caller arriving while the documents
    still describe the gate as unused, so the failure message asks for three
    things and calls none of them a bug.
    """

    GATE = "require_media_processing_allowed"

    #: Call sites that exist and are accounted for. Empty today. Growing this
    #: is a normal, expected change - see the failure message.
    EXPECTED_CALL_SITES: frozenset[str] = frozenset()

    #: The sentence in PROJECT_STATE that has to agree with the ledger.
    DOC_CLAIM = "chưa có caller nào trong"

    @classmethod
    def _call_sites(cls) -> set[str]:
        """Every *call* to the gate in ``src/``.

        ``ast.Call`` only, so the definition and the three docstrings that
        mention the name are excluded by construction rather than by filtering.
        That is the distinction a grep could not make, and the reason the count
        was read as four for a while.
        """
        sites: set[str] = set()
        for path in sorted(SRC.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and (
                    (isinstance(node.func, ast.Attribute) and node.func.attr == cls.GATE)
                    or (isinstance(node.func, ast.Name) and node.func.id == cls.GATE)
                ):
                    sites.add(f"{path.name}:{node.lineno}")
        return sites

    def test_the_call_sites_match_the_ledger(self) -> None:
        found = self._call_sites()
        assert found == set(self.EXPECTED_CALL_SITES), (
            f"call sites for {self.GATE}() changed: found {sorted(found)}, ledger "
            f"has {sorted(self.EXPECTED_CALL_SITES)}.\n"
            "This is NOT a product defect - wiring the gate up is what it is for. "
            "Three things are being asked for:\n"
            "  1. add the call site to EXPECTED_CALL_SITES here;\n"
            "  2. add a behavioural test proving that path actually refuses while "
            "consent is pending, because this ledger sees the call and not whether "
            "it blocks anything;\n"
            "  3. update PROJECT_STATE, which currently describes the gate as "
            "having no caller."
        )

    def test_the_documents_agree_with_the_ledger(self) -> None:
        """A two-way lock, so code and prose cannot drift apart.

        While the ledger is empty the claim has to be in the document; once a
        caller is recorded the claim has to be gone. Either half failing means
        somebody changed one and not the other, which is exactly the drift this
        project keeps finding by hand.
        """
        state = (Path(__file__).resolve().parent.parent / "PROJECT_STATE.md").read_text(
            encoding="utf-8"
        )
        claimed = self.DOC_CLAIM in state
        if not self.EXPECTED_CALL_SITES:
            assert claimed, (
                "the ledger says the gate has no caller, but PROJECT_STATE no longer "
                "says so. Restore the statement, or record the caller in "
                "EXPECTED_CALL_SITES if one was added."
            )
        else:
            assert not claimed, (
                "the ledger records a caller, but PROJECT_STATE still says the gate "
                "has none. Update the document to describe what the gate now guards."
            )


class TestWhereScopeAndSensitivityAreEnforced:
    """Two claims the documents make about layering, now measured.

    ``docs/spec.md`` records that **scope is bound at retrieval and by nothing
    below it** - ``answerability.assess`` has no ``scope`` parameter and
    ``Evidence.scope`` is not consumed - and it carries the status
    ``[CHỜ BẰNG CHỨNG]`` because nothing checked it. That is the shape this
    project has been caught by before: a claim that rests on reading.

    The second claim is about granularity. A recorded open question said the
    handoff wanted sensitivity per field while the code did it per card. It
    does not: the handoff lists ``sensitivity`` among a knowledge card's
    minimum fields, which is what the code implements. The thing that reads as
    field-level is ``visibility`` on a *profile*, a different entity.

    Neither test decides policy. *Which* scope a meeting question maps to is
    still the owner's call; this only pins where the mechanism lives.
    """

    #: The one module allowed to compare a card's scope, and the function
    #: inside it that binds scope to an answer. `conflicts` and
    #: `purge_scope` also compare scope, for a query and a deletion - which
    #: is why the function matters and the module alone is not enough.
    ENFORCING_MODULE = "knowledge.py"
    ENFORCING_FUNCTION = "retrieve"

    def test_assess_takes_no_scope_parameter(self) -> None:
        """Asked of the real signature, not of the source text."""
        import inspect

        from meetai.answerability import assess

        parameters = list(inspect.signature(assess).parameters)
        assert "scope" not in parameters, (
            f"assess() grew a scope parameter: {parameters}. Scope is bound at "
            "retrieval; a second place to bind it is a second place to get it "
            "wrong, and docs/spec.md says it is bound nowhere below retrieval."
        )

    def test_answerability_mentions_scope_only_in_prose(self) -> None:
        """Six mentions in that file, all of them documentation.

        Using :func:`code_tokens` rather than a substring count, because the
        distinction between a module that *talks about* scope and one that
        *uses* it is the whole claim.
        """
        source = (SRC / "answerability.py").read_text(encoding="utf-8")
        assert "scope" in source, "expected the module to discuss scope"
        assert "scope" not in code_tokens(ast.parse(source)), (
            "answerability.py now uses `scope` as code, not just in prose. If "
            "the layer really should bind scope, docs/spec.md's residual about "
            "it has to change too."
        )

    def test_the_scope_comparison_lives_in_the_retrieval_module(self) -> None:
        """The positive half: somebody must actually enforce it.

        Without this, deleting the comparison entirely would satisfy the two
        tests above - the layer below would still not bind scope, because
        nothing would.
        """
        per_function: dict[tuple[str, str], int] = {}
        for path in sorted(SRC.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            owner: dict[int, str] = {}
            for function in ast.walk(tree):
                if isinstance(function, ast.FunctionDef | ast.AsyncFunctionDef):
                    for inner in ast.walk(function):
                        owner[id(inner)] = function.name
            for node in ast.walk(tree):
                if isinstance(node, ast.Compare) and any(
                    isinstance(side, ast.Attribute) and side.attr == "scope"
                    for side in [node.left, *node.comparators]
                ):
                    key = (path.name, owner.get(id(node), "<module>"))
                    per_function[key] = per_function.get(key, 0) + 1

        # Asked of the *function*, not of the module. The module-level version
        # of this assertion passed while the retrieval filter was deleted,
        # because knowledge.py compares scope in three functions - `retrieve`,
        # `conflicts` and `purge_scope` - and two survivors kept the count
        # non-zero. A mutation found that; reading it did not.
        assert (self.ENFORCING_MODULE, self.ENFORCING_FUNCTION) in per_function, (
            f"{self.ENFORCING_FUNCTION}() no longer compares a card's scope; "
            f"found {sorted(per_function)}. Scope would be bound nowhere, and "
            "the layers below it do not bind it by design."
        )
        outside = {key for key in per_function if key[0] != self.ENFORCING_MODULE}
        assert outside == set(), (
            f"scope is compared outside the retrieval module: {sorted(outside)}. "
            "Two enforcement points mean two behaviours to keep in step."
        )

    def test_sensitivity_is_a_card_field_not_a_clause_field(self) -> None:
        """The granularity the handoff actually asks for.

        The handoff lists ``sensitivity`` among a knowledge card's minimum
        fields. A clause or a claim does not carry its own sensitivity, and if
        one ever did, the two could disagree about the same text - which is the
        reason to notice the change rather than to forbid it.
        """
        import dataclasses

        from meetai.answerability import EvidenceClause
        from meetai.knowledge import KnowledgeCard

        card_fields = {f.name for f in dataclasses.fields(KnowledgeCard)}
        assert "sensitivity" in card_fields
        assert "scope" in card_fields

        clause_fields = {f.name for f in dataclasses.fields(EvidenceClause)}
        assert "sensitivity" not in clause_fields, (
            "EvidenceClause gained a sensitivity of its own. Two places can "
            "then disagree about the same text; say which one wins before "
            "relaxing this."
        )


class TestTheAddressingClassifierHasNoCallerYet:
    """``classify_address`` is implemented, tested, and called by nothing.

    The behaviour is covered thoroughly elsewhere - an empty registry reaches
    no direct address, ``UNCLEAR`` is the default, a vocative alone does not
    permit a reply, turn context needs reliable speaker mapping. None of that
    is repeated here. What was **not** recorded anywhere is the wiring: no
    code in ``src/`` calls the classifier or builds an ``AliasRegistry``, so
    on every path that runs today the addressee is supplied by the caller.

    That is easy to over-read in the other direction. ``ResponseRequest``
    documents that ``address`` "comes from the addressing classifier, not from
    the model", which is a true statement of the **contract** - a proposal
    cannot assert it was spoken to - and is not a statement that a classifier
    is wired up. This project has already had one reader take exactly that
    step with the media gate, so the distinction is recorded rather than left
    to the next reading.

    **A caller appearing is not a defect.** It is the point of the module, and
    Phase 3 is where it happens. What this guards is a caller arriving while
    the documents still describe the classifier as unused.
    """

    CLASSIFIER = "classify_address"
    REGISTRY = "AliasRegistry"

    #: Call sites that exist and are accounted for. Empty today.
    EXPECTED_CALL_SITES: frozenset[str] = frozenset()

    #: The sentence in PROJECT_STATE that has to agree with the ledger.
    DOC_CLAIM = "classify_address() chua co caller nao trong src/"

    @classmethod
    def _sites(cls, names: tuple[str, ...]) -> set[str]:
        """Calls to any of ``names`` in ``src/``, by AST rather than by text.

        ``ast.Call`` only, so the definition, the ``__all__`` entry and the
        type annotation on a keyword argument are all excluded by
        construction - which is what a grep could not separate.
        """
        sites: set[str] = set()
        for path in sorted(SRC.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if not isinstance(node, ast.Call):
                    continue
                called = (
                    node.func.id
                    if isinstance(node.func, ast.Name)
                    else node.func.attr
                    if isinstance(node.func, ast.Attribute)
                    else None
                )
                if called in names:
                    sites.add(f"{path.name}:{node.lineno} {called}")
        return sites

    def test_nothing_in_src_calls_the_classifier_or_builds_a_registry(self) -> None:
        found = self._sites((self.CLASSIFIER, self.REGISTRY))
        assert found == set(self.EXPECTED_CALL_SITES), (
            f"addressing is now wired: {sorted(found)}, ledger has "
            f"{sorted(self.EXPECTED_CALL_SITES)}.\n"
            "This is NOT a defect - wiring it is what the module is for. Three "
            "things are being asked for:\n"
            "  1. add the call site to EXPECTED_CALL_SITES here;\n"
            "  2. add a behavioural test for that path, because this ledger sees "
            "the call and not whether the classifier's answer is respected;\n"
            "  3. update PROJECT_STATE, which currently records the classifier as "
            "having no caller."
        )

    def test_the_documents_agree_with_the_ledger(self) -> None:
        """Two-way lock, the same shape as the media gate's.

        While the ledger is empty the statement has to be in the document;
        once a caller is recorded it has to be gone. Either half failing means
        code and prose moved apart.
        """
        state = (
            pathlib.Path(__file__).resolve().parent.parent / "PROJECT_STATE.md"
        ).read_text(encoding="utf-8")
        claimed = self.DOC_CLAIM in state
        if not self.EXPECTED_CALL_SITES:
            assert claimed, (
                "the ledger says the classifier has no caller, but PROJECT_STATE "
                "no longer says so. Restore the statement, or record the caller."
            )
        else:
            assert not claimed, (
                "the ledger records a caller, but PROJECT_STATE still says there "
                "is none. Update the document to describe what is wired."
            )

    def test_the_scan_finds_a_caller_when_there_is_one(self) -> None:
        """Control: a scan that matches nothing passes for free.

        Runs the same matching over a source that does call both, and over one
        that only mentions them in prose and in an annotation - the two shapes
        that made a text search useless here.
        """
        wired = ast.parse(
            "def f(registry=None):\n"
            "    r = AliasRegistry()\n"
            "    return classify_address('hi', registry=r)\n"
        )
        called = {
            node.func.id
            for node in ast.walk(wired)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        assert {"AliasRegistry", "classify_address"} <= called

        quiet = ast.parse(
            '"""classify_address is not called here, and AliasRegistry is not built."""\n'
            "def g(registry: AliasRegistry | None = None) -> None:\n"
            "    return None\n"
        )
        assert [n for n in ast.walk(quiet) if isinstance(n, ast.Call)] == []


class TestNothingProducesAnAbstentionUtteranceYet:
    """``silence()``, ``followup()`` and ``ASK_CLARIFICATION`` have no producer.

    All three are *permitted* and well covered as contracts:
    ``test_authority.py::TestAbstentionIsAlwaysAvailable`` asserts both helpers
    are always allowed and need no confidence or evidence, and
    ``test_boundary.py`` asserts a non-speaking proposal carries nothing to the
    sink. None of that is repeated here. What was **not** recorded anywhere is
    that nothing in ``src/`` ever *constructs* one.

    Why that distinction earns a test rather than a comment. ``spec.md`` row
    P-9 reads "missing / conflicting / expired / wrong-scope evidence -> do not
    speculate, **say the operator is needed**", and names ``response.followup``
    among its mechanisms. The first half is enforced and measured: a speak
    proposal citing nothing comes back ``allowed=False`` with the violation
    ``cite_without_citation``. The second half is not what happens. The verdict
    carries ``added_flags``, ``allowed``, ``rules`` and ``violations`` - and no
    replacement proposal - so the refusal ends in silence. The deferral
    utterance is a constructor nobody calls.

    Those are different behaviours for anyone in the room: saying nothing is
    not the same as saying "this needs the operator". This project has already
    had one reader take the available-means-wired step with the media gate, so
    the distinction is recorded rather than left to the next reading.

    **A producer appearing is not a defect.** It is the point of the helpers,
    and a model-driven path is where one would be built. What this guards is a
    producer arriving while the documents still describe the refusal as a
    spoken deferral.
    """

    HELPERS = ("silence", "followup")
    ACT = "ASK_CLARIFICATION"

    #: Producers that exist and are accounted for. Empty today.
    EXPECTED_PRODUCERS: frozenset[str] = frozenset()

    #: The sentence in spec.md that has to agree with the ledger.
    DOC_CLAIM = "chưa có producer nào trong `src/`"

    @classmethod
    def _producers(cls) -> set[str]:
        """Producers of the helpers, plus uses of the act, by AST not by text.

        ``ast.Call`` for the helpers excludes their own ``def`` lines, and
        ``ast.Attribute`` for the act excludes the enum member's definition, an
        ``__all__`` entry and a bare mention in a docstring - the shapes a text
        search cannot separate.
        """
        found: set[str] = set()
        for path in sorted(SRC.rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    called = (
                        node.func.id
                        if isinstance(node.func, ast.Name)
                        else node.func.attr
                        if isinstance(node.func, ast.Attribute)
                        else None
                    )
                    if called in cls.HELPERS:
                        found.add(f"{path.name}:{node.lineno} {called}()")
                elif isinstance(node, ast.Attribute) and node.attr == cls.ACT:
                    found.add(f"{path.name}:{node.lineno} {cls.ACT}")
        return found

    def test_no_module_in_src_produces_one(self) -> None:
        found = self._producers()
        assert found == set(self.EXPECTED_PRODUCERS), (
            f"an abstention utterance now has a producer: {sorted(found)}, "
            f"ledger has {sorted(self.EXPECTED_PRODUCERS)}.\n"
            "This is NOT a defect - producing one is what the helpers are for. "
            "Three things are being asked for:\n"
            "  1. add the producer to EXPECTED_PRODUCERS here;\n"
            "  2. add a behavioural test for that path, because this ledger sees "
            "the construction and not whether the deferral is actually spoken;\n"
            "  3. update docs/spec.md row P-9, which currently records that the "
            "deferral utterance has no producer."
        )

    def test_the_refusal_really_ends_in_silence_rather_than_a_deferral(self) -> None:
        """The behaviour the ledger is about, asserted against the real gate.

        Without this the ledger would be a statement about call sites only.
        Here the claim is the user-visible one: evidence is missing, so the
        proposal is refused, and the verdict offers nothing to say instead.
        """
        from meetai.authority import evaluate_response
        from meetai.content import MeetingContent
        from meetai.response import (
            AddressContext,
            ProposedResponse,
            ResponseDecision,
            SpeechAct,
        )

        verdict = evaluate_response(
            ProposedResponse(
                decision=ResponseDecision.SPEAK,
                text=MeetingContent("Ngan sach du an la 240 trieu."),
                intent=SpeechAct.CITE_APPROVED_POSITION,
                confidence=0.9,
            ),
            address=AddressContext(directly_addressed=True),
        )
        assert verdict.allowed is False
        # ``AuthorityVerdict`` is a slots dataclass, so it has no ``__dict__``
        # and ``vars()`` raises. Ask the dataclass what fields it declares.
        carried = {
            f.name
            for f in dataclasses.fields(verdict)
            if isinstance(getattr(verdict, f.name), ProposedResponse)
        }
        assert carried == set(), (
            f"the verdict now hands back a proposal ({sorted(carried)}), so a "
            "refusal can become a spoken deferral. Update P-9 and this ledger."
        )

    def test_the_documents_agree_with_the_ledger(self) -> None:
        """Two-way lock, the same shape as the other two ledgers here."""
        spec = (
            pathlib.Path(__file__).resolve().parent.parent / "docs" / "spec.md"
        ).read_text(encoding="utf-8")
        claimed = self.DOC_CLAIM in spec
        if not self.EXPECTED_PRODUCERS:
            assert claimed, (
                "the ledger says nothing produces an abstention utterance, but "
                "docs/spec.md no longer records that. Restore the statement in "
                "row P-9, or record the producer."
            )
        else:
            assert not claimed, (
                "the ledger records a producer, but docs/spec.md still says "
                "there is none. Update row P-9 to describe what is wired."
            )

    def test_the_scan_finds_a_producer_when_there_is_one(self) -> None:
        """Control: a scan that matches nothing passes for free.

        Runs the same matching over a source that really produces all three,
        and over one that only mentions them in prose, in ``__all__`` and in an
        annotation - the shapes that made a text search useless here.
        """
        wired = ast.parse(
            "def f():\n"
            "    a = silence()\n"
            "    b = followup()\n"
            "    c = SpeechAct.ASK_CLARIFICATION\n"
            "    return a, b, c\n"
        )
        calls = {
            node.func.id
            for node in ast.walk(wired)
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
        }
        attrs = {node.attr for node in ast.walk(wired) if isinstance(node, ast.Attribute)}
        assert {"silence", "followup"} <= calls
        assert "ASK_CLARIFICATION" in attrs

        quiet = ast.parse(
            '"""silence and followup are not called, ASK_CLARIFICATION unused."""\n'
            '__all__ = ["silence", "followup", "ASK_CLARIFICATION"]\n'
            "def g(x: SpeechAct = None) -> None:\n"
            "    return None\n"
        )
        assert [n for n in ast.walk(quiet) if isinstance(n, ast.Call)] == []
        assert [
            n
            for n in ast.walk(quiet)
            if isinstance(n, ast.Attribute) and n.attr == "ASK_CLARIFICATION"
        ] == []
