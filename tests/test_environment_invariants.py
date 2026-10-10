"""Invariants about the installed environment and the shape of the source.

These are the checks that would otherwise be a sentence in a document nobody
re-reads. They assert properties of the venv and of the code, so that a future
``uv add`` or a convenient shortcut breaks a test instead of a guarantee.
"""

from __future__ import annotations

import ast
import importlib.metadata
import importlib.util
import re
from pathlib import Path

import pytest

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
