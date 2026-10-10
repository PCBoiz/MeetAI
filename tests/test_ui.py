"""Tests for the local web UI.

The security tests are the point of this file. Each one is written so that
deleting the mechanism it guards fails it, and each names the attack it
represents rather than describing the mechanism.
"""

from __future__ import annotations

import ast
from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from meetai.capabilities import current_capabilities
from meetai.settings import Settings, load_settings
from meetai.supervisor import ModelState, ModelSwitch, RunState, Supervisor
from meetai.ui import (
    REQUEST_HEADER,
    TELEMETRY_OFF,
    UiDependencies,
    build_status,
    create_app,
    render_page,
)

SRC = Path(__file__).resolve().parent.parent / "src" / "meetai"

STATE_CHANGING = [
    "/api/start",
    "/api/stop",
    "/api/model/on",
    "/api/model/off",
    "/api/kill",
]


@pytest.fixture
def settings() -> Settings:
    return load_settings(env={}, env_file=None)


@pytest.fixture
def supervisor(settings: Settings) -> Supervisor:
    return Supervisor(
        settings_allows_media=lambda: settings.media_processing_allowed,
        model=ModelSwitch(loader=lambda: ModelState.READY),
    )


@pytest.fixture
def deps(settings: Settings, supervisor: Supervisor) -> UiDependencies:
    return UiDependencies(settings=settings, supervisor=supervisor)


@pytest.fixture
def client(deps: UiDependencies) -> Iterator[TestClient]:
    app = create_app(deps)
    with TestClient(app, base_url="http://127.0.0.1:8765") as test_client:
        yield test_client


# -------------------------------------------------------------------- #
# Telemetry
# -------------------------------------------------------------------- #


class TestTelemetryIsOff:
    def test_resolved_config_matches_exactly(self, deps: UiDependencies) -> None:
        """Exact-dict equality, not a subset.

        A subset assertion passes when a future FastAPI adds a seventh signal
        defaulting to on. Reading the private `_telemetry` is correct here: it
        is the resolved configuration and the only observable.
        """
        app = create_app(deps)
        assert app._telemetry == {
            "tracer_provider": None,
            "meter_provider": None,
            "logger_provider": None,
            "tracing": False,
            "metrics": False,
            "logs": False,
            "operation_spans": False,
            "auto_configure": False,
            "exclude": None,
        }

    def test_every_signal_in_the_constant_is_false(self) -> None:
        assert all(value is False for value in TELEMETRY_OFF.values())

    def test_the_default_would_have_been_on(self) -> None:
        """Pins what the explicit configuration is opting out of.

        If a future version flipped the defaults to off, this test fails and
        the explicit config becomes redundant rather than load-bearing - which
        is worth knowing deliberately.
        """
        from fastapi import FastAPI

        default = FastAPI()
        assert default._telemetry["tracing"] is True
        assert default._telemetry["logs"] is True
        assert default._telemetry["auto_configure"] is True

    def test_native_telemetry_middleware_is_disabled(self, deps: UiDependencies) -> None:
        """The behavioural half: this is what decides whether it runs at all."""
        app = create_app(deps)
        assert app._native_telemetry.enabled() is False

    def test_only_one_fastapi_constructor_exists(self) -> None:
        """A second bare `FastAPI()` would get every telemetry default.

        Checked over the source, because the risk is a future router module or
        test helper constructing its own app.
        """
        offenders: list[str] = []
        for path in SRC.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"))
            for node in ast.walk(tree):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "FastAPI"
                ):
                    offenders.append(f"{path.name}:{node.lineno}")
        assert len(offenders) == 1, offenders
        assert offenders[0].startswith("ui.py")


# -------------------------------------------------------------------- #
# Browser-side egress
# -------------------------------------------------------------------- #


class TestNoThirdPartyEgress:
    @pytest.mark.parametrize("path", ["/docs", "/redoc", "/openapi.json"])
    def test_builtin_docs_are_off(self, client: TestClient, path: str) -> None:
        """They serve HTML pointing at four third-party hosts.

        Opening one makes the operator's browser contact a CDN, which the
        MEETAI_* and OTEL_* guards cannot see: the request comes from the
        browser, not this process.
        """
        assert client.get(path).status_code == 404

    @pytest.mark.parametrize(
        "host",
        ["cdn.jsdelivr.net", "fonts.googleapis.com", "fastapi.tiangolo.com"],
    )
    def test_no_page_references_a_cdn(self, client: TestClient, host: str) -> None:
        assert host not in client.get("/").text

    def test_no_absolute_external_url_in_the_page(self, client: TestClient) -> None:
        """Catches a future template that hand-rolls a CDN link."""
        body = client.get("/").text
        for scheme in ("http://", "https://", "//cdn", "//fonts"):
            if scheme in ("http://", "https://"):
                # Only loopback is acceptable, and only in the displayed URL.
                for fragment in body.split(scheme)[1:]:
                    host = fragment.split("/")[0].split('"')[0].split("'")[0]
                    assert host.startswith(("127.0.0.1", "[::1]")), host
            else:
                assert scheme not in body

    def test_no_cors_middleware(self, deps: UiDependencies) -> None:
        """Installing it could only loosen the default.

        With no CORS middleware, no Access-Control-Allow-Origin is ever
        emitted and no cross-origin page can read a response.
        """
        app = create_app(deps)
        installed = {getattr(m.cls, "__name__", str(m.cls)) for m in app.user_middleware}
        assert "CORSMiddleware" not in installed

    def test_source_mentions_no_cors_configuration(self) -> None:
        """`allow_private_network=True` explicitly invites public pages in."""
        source = (SRC / "ui.py").read_text(encoding="utf-8")
        for forbidden in ("allow_origins", "allow_private_network"):
            assert forbidden not in source

    def test_no_websocket_route(self, deps: UiDependencies) -> None:
        """Starlette performs no Origin check on a WebSocket handshake.

        So a socket is reachable cross-origin, bidirectionally - strictly
        worse than HTTP, where response reading is at least blocked. Status is
        polled over plain HTTP instead.
        """
        app = create_app(deps)
        assert not any(type(route).__name__ == "WebSocketRoute" for route in app.routes)


# -------------------------------------------------------------------- #
# CSRF
# -------------------------------------------------------------------- #


class TestCsrfHeader:
    @pytest.mark.parametrize("path", STATE_CHANGING)
    def test_state_change_without_the_header_is_refused(
        self, client: TestClient, path: str
    ) -> None:
        """Any open webpage can POST here; the side effect would happen.

        CORS does not help - it governs reading responses, never sending
        simple requests.
        """
        response = client.post(path)
        assert response.status_code == 403
        assert response.json()["error"] == "missing_request_header"

    def test_a_refused_kill_does_not_fire_the_kill_switch(
        self, client: TestClient, supervisor: Supervisor
    ) -> None:
        """The assertion that matters: refused means nothing happened."""
        client.post("/api/kill")
        assert supervisor.kill_switch.engaged is False
        assert supervisor.state is not RunState.KILLED

    def test_a_refused_start_does_not_start(
        self, client: TestClient, supervisor: Supervisor
    ) -> None:
        client.post("/api/start")
        assert supervisor.is_running is False

    @pytest.mark.parametrize("path", STATE_CHANGING)
    def test_state_change_with_the_header_is_accepted(
        self, client: TestClient, path: str
    ) -> None:
        response = client.post(path, headers={REQUEST_HEADER: "1"})
        assert response.status_code in (200, 409)

    @pytest.mark.parametrize("path", STATE_CHANGING)
    def test_get_does_not_change_state(self, client: TestClient, path: str) -> None:
        """A GET endpoint is reachable by `<img src>`."""
        assert client.get(path).status_code == 405

    def test_wrong_header_value_is_refused(self, client: TestClient) -> None:
        response = client.post("/api/kill", headers={REQUEST_HEADER: "0"})
        assert response.status_code == 403


# -------------------------------------------------------------------- #
# Host header
# -------------------------------------------------------------------- #


class TestHostHeader:
    @pytest.mark.parametrize(
        "host", ["evil.com", "localhost:8765", "127.0.0.1.nip.io", "0.0.0.0:8765"]
    )
    def test_foreign_host_is_refused(self, client: TestClient, host: str) -> None:
        """Closes DNS rebinding.

        An attacker page whose hostname re-resolves to 127.0.0.1 keeps its own
        origin, so same-origin policy stops protecting and it can read
        responses. `localhost` is refused deliberately: it is a name resolved
        at bind time, matching the settings rail.
        """
        assert client.get("/", headers={"Host": host}).status_code == 400

    def test_the_bound_host_is_accepted(self, client: TestClient) -> None:
        assert client.get("/", headers={"Host": "127.0.0.1:8765"}).status_code == 200


# -------------------------------------------------------------------- #
# Honest state
# -------------------------------------------------------------------- #


class TestReadinessHonesty:
    def test_never_reports_ready_for_a_live_meeting(self, client: TestClient) -> None:
        """The evidence gates are open, so this is False unconditionally."""
        assert client.get("/api/status").json()["ready_for_live_meeting"] is False

    def test_the_evidence_gate_is_always_a_blocker(self, client: TestClient) -> None:
        blockers = client.get("/api/status").json()["not_ready_because"]
        assert "evidence_gate_0s_0p_0c_open" in blockers

    def test_ready_stays_false_even_fully_started(
        self, client: TestClient, supervisor: Supervisor
    ) -> None:
        client.post("/api/start", headers={REQUEST_HEADER: "1"})
        client.post("/api/model/on", headers={REQUEST_HEADER: "1"})
        assert supervisor.media_allowed() is False  # consent still pending
        assert client.get("/api/status").json()["ready_for_live_meeting"] is False

    def test_page_states_it_is_not_ready(self, client: TestClient) -> None:
        assert "chưa sẵn sàng" in client.get("/").text

    def test_undecided_model_state_is_not_rendered_as_on(
        self, settings: Settings
    ) -> None:
        """A probe in flight must render as undecided, not as working."""
        supervisor = Supervisor(
            settings_allows_media=lambda: True,
            model=ModelSwitch(loader=lambda: ModelState.LOADING),
        )
        supervisor.model.turn_on()
        status = build_status(UiDependencies(settings=settings, supervisor=supervisor))
        assert status["supervisor"]["model_state_decided"] is False
        assert "model_state_undecided" in status["not_ready_because"]
        assert "chưa xác định" in render_page(status)

    def test_model_error_is_distinguishable_from_never_built(
        self, settings: Settings
    ) -> None:
        """Two different facts; only one warrants a retry."""
        supervisor = Supervisor(settings_allows_media=lambda: True, model=ModelSwitch())
        supervisor.model.turn_on()
        status = build_status(UiDependencies(settings=settings, supervisor=supervisor))
        assert status["supervisor"]["model_state"] == "error"
        assert status["supervisor"]["model_state_decided"] is True

    def test_every_off_capability_renders_its_reason(self, client: TestClient) -> None:
        body = client.get("/").text
        for name, entry in current_capabilities().as_dict().items():
            if not entry["available"]:
                assert str(entry["blocked_reason"]) in body, name

    def test_pending_decisions_are_shown(self, client: TestClient) -> None:
        body = client.get("/").text
        assert "consent_mode" in body
        assert "late_join_policy" in body


class TestControlsDoNotOverreach:
    def test_start_does_not_join_or_enable_audio(
        self, client: TestClient, supervisor: Supervisor
    ) -> None:
        """A Start that quietly joined a meeting would be the worst reading."""
        client.post("/api/start", headers={REQUEST_HEADER: "1"})
        assert supervisor.is_running is True
        assert supervisor.model.state is ModelState.OFF
        assert supervisor.media_allowed() is False

    def test_model_on_does_not_enable_media(
        self, client: TestClient, supervisor: Supervisor
    ) -> None:
        client.post("/api/model/on", headers={REQUEST_HEADER: "1"})
        assert supervisor.model.state is ModelState.READY
        assert supervisor.media_allowed() is False  # not running, consent pending

    def test_kill_is_irreversible_through_the_api(
        self, client: TestClient, supervisor: Supervisor
    ) -> None:
        client.post("/api/start", headers={REQUEST_HEADER: "1"})
        client.post("/api/kill", headers={REQUEST_HEADER: "1"})
        assert supervisor.kill_switch.engaged is True

        response = client.post("/api/start", headers={REQUEST_HEADER: "1"})
        assert response.status_code == 409
        assert supervisor.state is RunState.KILLED

    def test_page_says_start_does_not_join(self, client: TestClient) -> None:
        assert "không</strong> join Discord" in client.get("/").text

    def test_no_control_sets_a_pending_policy(self, deps: UiDependencies) -> None:
        """No UI may choose consent, late join or persistence on the operator's
        behalf."""
        app = create_app(deps)
        paths = {route.path for route in app.routes if hasattr(route, "path")}
        for forbidden in ("consent", "late_join", "persist", "retention"):
            assert not any(forbidden in path for path in paths), forbidden


# -------------------------------------------------------------------- #
# No content anywhere
# -------------------------------------------------------------------- #


class TestNoContentOrSecretsServed:
    @staticmethod
    def _leaf_keys(node: object, found: set[str] | None = None) -> set[str]:
        keys = set() if found is None else found
        if isinstance(node, dict):
            for key, value in node.items():
                keys.add(str(key))
                TestNoContentOrSecretsServed._leaf_keys(value, keys)
        elif isinstance(node, list):
            for item in node:
                TestNoContentOrSecretsServed._leaf_keys(item, keys)
        return keys

    def test_status_payload_has_no_content_keys(self, client: TestClient) -> None:
        """Matched on exact key names, not substrings.

        A substring search is wrong here and the first version of this test was:
        `persist_transcript` is the *name of a boolean flag*, so searching the
        serialised payload for "transcript" flagged a setting that carries no
        content at all. The question is whether a key *holds* content, which
        only an exact name can answer.
        """
        keys = self._leaf_keys(client.get("/api/status").json())
        forbidden = {
            "transcript",
            "text",
            "utterance",
            "content",
            "claim",
            "rationale",
            "audio",
            "pcm",
            "frame",
            "display_name",
            "participant_name",
            "summary",
            "prompt",
            "reply",
            "token",
            "secret",
        }
        assert not (keys & forbidden), keys & forbidden

    def test_the_served_key_set_is_a_reviewed_snapshot(self, client: TestClient) -> None:
        """Any new key in the payload must be reviewed, content-bearing or not.

        A name-shape heuristic was tried twice and was wrong both times:
        `transcript` as a substring and `_transcript` as a suffix both match
        `persist_transcript`, a boolean flag that carries nothing. Whether a
        key holds content is not decidable from its spelling.

        So the test pins the exact set instead. No false positives, and it
        fails on *any* addition - which is the right trigger, because "does
        this new field carry content" needs a human to answer.
        """
        keys = self._leaf_keys(client.get("/api/status").json())
        expected = {
            # Top level
            "ready_for_live_meeting",
            "not_ready_because",
            "supervisor",
            "settings",
            "capabilities",
            "pending_decisions",
            # Supervisor.status()
            "run_state",
            "model_state",
            "model_detail",
            "model_state_decided",
            "kill_engaged",
            "kill_reason",
            "settings_allows_media",
            "media_allowed",
            # Settings.redacted_summary()
            "ui_host",
            "ui_port",
            "state_dir",
            "consent_mode",
            "late_join_policy",
            "persist_transcript",
            "persist_notes",
            "persist_reply_journal",
            "persist_raw_audio_debug",
            "raw_audio_debug_acknowledged",
            "any_content_persistence_enabled",
            "media_processing_allowed",
            "requested_external_ai",
            "requested_live_discord_voice",
            "discord_bot_token_configured",
            "google_oauth_client_secret_configured",
            # Capability entry fields
            "available",
            "blocked_reason",
            "blocked_by",
            "operator_can_act",
            "synthetic",
        } | set(current_capabilities().as_dict())
        assert keys == expected, {
            "added": sorted(keys - expected),
            "removed": sorted(expected - keys),
        }

    def test_credentials_are_presence_only(self, client: TestClient) -> None:
        canary = "SENTINEL-UI-TOKEN-MUST-NOT-BE-SERVED"
        from pydantic import SecretStr

        settings = load_settings(
            env={}, env_file=None, discord_bot_token=SecretStr(canary)
        )
        supervisor = Supervisor(settings_allows_media=lambda: True)
        app = create_app(UiDependencies(settings=settings, supervisor=supervisor))
        with TestClient(app, base_url="http://127.0.0.1:8765") as local:
            assert canary not in local.get("/api/status").text
            assert canary not in local.get("/").text
            assert local.get("/api/status").json()["settings"][
                "discord_bot_token_configured"
            ]

    def test_no_route_returns_meeting_content(self, deps: UiDependencies) -> None:
        """The real control against a local-process adversary is that this UI
        has nothing worth stealing. That is a design property to preserve."""
        app = create_app(deps)
        paths = sorted(route.path for route in app.routes if hasattr(route, "path"))
        assert paths == [
            "/",
            "/api/kill",
            "/api/model/off",
            "/api/model/on",
            "/api/start",
            "/api/status",
            "/api/stop",
        ]

    def test_page_escapes_rendered_values(self) -> None:
        """Everything rendered is metadata this process produced, but a reason
        string is still prose someone edits."""
        from meetai.ui import _escape

        assert _escape("<script>x</script>") == "&lt;script&gt;x&lt;/script&gt;"
        assert _escape('a"b') == "a&quot;b"


class TestDebugIsOff:
    def test_debug_mode_is_off(self, deps: UiDependencies) -> None:
        """debug=True turns tracebacks into HTTP responses - the same leak
        class as printing a ValidationError."""
        assert create_app(deps).debug is False


class TestServeEntryPoint:
    """The ordering and the failure mode, which are both easy to get wrong."""

    def test_configuration_is_validated_before_any_socket(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A guard that runs after the bind is decoration.

        With an egress variable set, `serve` must refuse before uvicorn is
        reached at all - so the spy must never be called.
        """
        from meetai import cli

        called: list[str] = []
        monkeypatch.setattr(
            "uvicorn.run", lambda *a, **k: called.append("ran"), raising=True
        )
        monkeypatch.setenv("OTEL_EXPORTER_OTLP_ENDPOINT", "http://x.example:4318")

        assert cli.main(["serve"]) == cli.EXIT_CONFIG_INVALID
        assert called == []

    def test_bind_failure_is_a_loud_refusal(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """uvicorn raises SystemExit, not OSError, on a bind failure.

        Measured, not assumed: an `except OSError` here never fired, and the
        process exited 3 - which collides with EXIT_UI_UNAVAILABLE, so a
        squatted port was reported to the operator as a missing extra.
        """
        from meetai import cli

        def exits(*_args: object, **_kwargs: object) -> None:
            raise SystemExit(3)

        monkeypatch.setattr("uvicorn.run", exits, raising=True)
        assert cli.main(["serve"]) == cli.EXIT_UI_BIND_FAILED

        err = capsys.readouterr().err
        assert "Khong bind duoc cong" in err
        assert "KHONG khoi dong" in err

    def test_the_port_is_never_retried_elsewhere(self) -> None:
        """Silently moving the UI is the squatting attack, self-inflicted.

        The operator's bookmark is the trust anchor, so a failed bind must not
        become a successful bind on another number.
        """
        source = (
            Path(__file__).resolve().parent.parent / "src" / "meetai" / "cli.py"
        ).read_text(encoding="utf-8")
        serve = source[source.index("def _serve") :]
        assert "ui_port + 1" not in serve
        assert "range(" not in serve
        assert serve.count("uvicorn.run") == 1

    def test_access_log_is_off(self) -> None:
        """Access logs carry request paths and query strings."""
        source = (
            Path(__file__).resolve().parent.parent / "src" / "meetai" / "cli.py"
        ).read_text(encoding="utf-8")
        assert "access_log=False" in source
        assert "log_config=None" in source

    def test_startup_banner_says_it_is_not_ready(
        self, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
    ) -> None:
        from meetai import cli

        monkeypatch.setattr("uvicorn.run", lambda *a, **k: None, raising=True)
        assert cli.main(["serve"]) == cli.EXIT_OK
        assert "CHUA san sang" in capsys.readouterr().err
