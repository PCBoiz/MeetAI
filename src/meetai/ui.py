"""Local web UI for the supervisor (slice S0.6).

Loopback only, no authentication, and the reasoning for both is in
``docs/adr/0003``. The short version: the adversary that matters is a webpage
the operator already has open, because that one is reachable with no prior
access to the machine. An adversary who is already running code as the
operator can read ``.env`` and this process's memory, so nothing served here
can defend against them - and the real control for that threat is that this UI
**has nothing worth stealing**. No endpoint returns meeting content. That is a
design property to preserve, not a control to add.

Four non-obvious choices, each closing something verified rather than imagined:

1. **``create_app`` is the only place ``FastAPI(...)`` is constructed**, and a
   test enforces it. FastAPI 0.142 ships a first-party telemetry subsystem
   whose signal flags all default to ``True`` and whose exporter endpoint comes
   from ``OTEL_EXPORTER_OTLP_ENDPOINT``; its ``logs`` signal records exception
   messages *and* request bodies *and* validation errors including the original
   input values. A second bare ``FastAPI()`` anywhere would get all of that.

2. **The built-in docs are off.** ``/docs`` and ``/redoc`` serve HTML that
   points at ``cdn.jsdelivr.net``, ``fonts.googleapis.com`` and
   ``fastapi.tiangolo.com``. Opening them makes the operator's browser contact
   four third-party hosts. The ``MEETAI_*`` and ``OTEL_*`` guards cannot see
   that, because the requests come from the browser rather than this process.

3. **State-changing requests need a header a form cannot set.** Any open
   webpage can ``fetch('http://127.0.0.1:8765/api/kill', {method:'POST'})``
   and the side effect happens, opaque response or not. CORS does not help:
   it governs reading responses, never sending simple requests. Requiring
   ``X-MeetAI-Request`` forces a preflight that nothing answers. This is a
   header check rather than a CSRF token because the token would need
   server-side state, a cookie and an expiry policy to buy the same guarantee
   against the same adversary.

4. **No ``CORSMiddleware``, and no WebSocket.** Installing CORS could only
   loosen the default, which is that no cross-origin page can read a response.
   Starlette performs **no** ``Origin`` check on WebSocket handshakes at all,
   so a socket would be reachable cross-origin, bidirectionally - strictly
   worse than HTTP. Status is polled over plain HTTP instead.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.telemetry import TelemetryConfig
from starlette.middleware.trustedhost import TrustedHostMiddleware

from meetai.capabilities import CapabilityReport, current_capabilities
from meetai.errors import MeetAIError
from meetai.logging_setup import get_logger
from meetai.settings import Settings
from meetai.supervisor import Supervisor

# FastAPI is imported at module scope rather than inside the factory, and that
# is load-bearing rather than stylistic: with `from __future__ import
# annotations` every annotation is a string, and FastAPI resolves a route
# handler's annotations against the *module* globals. A lazily imported
# `Request` is a local name, so `request: Request` resolved to nothing and
# FastAPI treated it as a required query parameter - every POST returned 422.
#
# The cost is that importing this module needs the `ui` extra. The caller
# handles that: `meetai.cli` imports this module inside the `serve` command and
# reports a UiError if the extra is missing, so the rest of MeetAI stays
# importable without it.

REQUEST_HEADER = "X-MeetAI-Request"
"""Header required on every state-changing request.

A ``<form>`` cannot set it, and ``fetch`` setting it triggers a preflight that
no middleware here answers. Five lines, and it closes the one path that is
exploitable with no foothold on the machine.
"""

TELEMETRY_OFF: TelemetryConfig = {
    "tracing": False,
    "metrics": False,
    "logs": False,
    "operation_spans": False,
    "auto_configure": False,
}
"""Every telemetry signal FastAPI 0.142 offers, explicitly off.

Declared as a module constant so a test can assert the resolved configuration
against it. ``auto_configure=False`` is defence in depth rather than the
load-bearing switch: with all three signals off the exporter setup returns
before it would import the SDK. The signal flags are what matter.
"""


class UiError(MeetAIError):
    """The UI could not start."""


@dataclass(frozen=True, slots=True)
class UiDependencies:
    """What the UI needs, injected.

    The routes never import ``Settings`` or build a ``Supervisor`` themselves,
    so the app can be exercised in a test without touching the environment -
    which is also how the bind-ordering test checks that configuration is
    validated *before* a socket exists.
    """

    settings: Settings
    supervisor: Supervisor
    capabilities: Callable[[], CapabilityReport] = current_capabilities


def build_status(deps: UiDependencies) -> dict[str, Any]:
    """The whole payload the UI renders. Metadata only, by construction.

    Composed from three sources that already restrict themselves to metadata:
    ``Settings.redacted_summary``, ``Supervisor.status`` and
    ``CapabilityReport.as_dict``. There is deliberately no fourth source and no
    endpoint that returns a transcript, an utterance or a participant name.

    ``readiness`` is computed here rather than left to the template, so the
    answer is the same in the HTML and in the JSON and a test can assert it
    once.
    """
    supervisor = deps.supervisor.status()
    settings = deps.settings.redacted_summary()
    capabilities = deps.capabilities().as_dict()

    blockers: list[str] = []
    if supervisor["kill_engaged"]:
        blockers.append("kill_switch_engaged")
    if supervisor["run_state"] != "running":
        blockers.append("supervisor_not_running")
    if not supervisor["settings_allows_media"]:
        blockers.append("policy_pending_decision")
    if not supervisor["model_state_decided"]:
        blockers.append("model_state_undecided")
    elif supervisor["model_state"] != "ready":
        blockers.append("model_not_ready")
    blockers.append("evidence_gate_0s_0p_0c_open")

    return {
        "ready_for_live_meeting": False,
        "not_ready_because": blockers,
        "supervisor": supervisor,
        "settings": settings,
        "capabilities": capabilities,
        "pending_decisions": settings["pending_decisions"],
    }


def create_app(deps: UiDependencies) -> FastAPI:
    """Build the one and only FastAPI application.

    Everything that could be set wrongly is set here, so the test asserting
    the resolved telemetry configuration has exactly one place to watch.
    """
    log = get_logger("ui")

    app = FastAPI(
        telemetry=TELEMETRY_OFF,
        # The built-in docs load scripts and fonts from four third-party CDNs.
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        # debug=True turns tracebacks into HTTP responses, which is the same
        # leak class as printing a ValidationError.
        debug=False,
        title="MeetAI supervisor",
    )

    # Closes DNS rebinding: an attacker page whose hostname re-resolves to
    # 127.0.0.1 keeps its own origin, so same-origin policy stops protecting
    # and it can read responses. Rejecting any Host but the literal bind
    # address is the listen-side rail extended to the request side.
    #
    # `localhost` is deliberately absent, matching the settings rail: it is a
    # *name* resolved at bind time, and allowing it reopens exactly this.
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[
            f"{deps.settings.ui_host}:{deps.settings.ui_port}",
            deps.settings.ui_host,
        ],
    )

    def require_request_header(request: Request) -> JSONResponse | None:
        if request.headers.get(REQUEST_HEADER) != "1":
            log.warning(
                "state change refused",
                extra={"event": "ui_csrf_refused", "outcome": "refused"},
            )
            return JSONResponse(
                status_code=403,
                content={
                    "error": "missing_request_header",
                    "detail": (
                        f"Yeu cau doi trang thai phai co header {REQUEST_HEADER}: 1. "
                        "Day la chan CSRF: mot trang web bat ky khong dat duoc "
                        "header nay ma khong kich hoat preflight."
                    ),
                },
            )
        return None

    @app.get("/api/status")
    def api_status() -> dict[str, Any]:
        return build_status(deps)

    @app.post("/api/start")
    def api_start(request: Request) -> Any:
        """Bring up local components only. Does **not** join any platform."""
        refusal = require_request_header(request)
        if refusal is not None:
            return refusal
        try:
            deps.supervisor.start()
        except MeetAIError as exc:
            return JSONResponse(
                status_code=409,
                content={"error": type(exc).__name__, "detail": str(exc)},
            )
        log.info("supervisor started", extra={"event": "ui_start", "outcome": "ok"})
        return build_status(deps)

    @app.post("/api/stop")
    def api_stop(request: Request) -> Any:
        refusal = require_request_header(request)
        if refusal is not None:
            return refusal
        deps.supervisor.stop()
        log.info("supervisor stopped", extra={"event": "ui_stop", "outcome": "ok"})
        return build_status(deps)

    @app.post("/api/model/on")
    def api_model_on(request: Request) -> Any:
        """Load the model runtime. Does **not** enable audio or external AI."""
        refusal = require_request_header(request)
        if refusal is not None:
            return refusal
        state = deps.supervisor.model.turn_on()
        log.info(
            "model switch",
            extra={"event": "ui_model_on", "state": state.value},
        )
        return build_status(deps)

    @app.post("/api/model/off")
    def api_model_off(request: Request) -> Any:
        refusal = require_request_header(request)
        if refusal is not None:
            return refusal
        deps.supervisor.model.turn_off()
        log.info("model switch", extra={"event": "ui_model_off", "state": "off"})
        return build_status(deps)

    @app.post("/api/kill")
    def api_kill(request: Request) -> Any:
        """Engage the kill switch. Irreversible within this process."""
        refusal = require_request_header(request)
        if refusal is not None:
            return refusal
        deps.supervisor.kill("engaged from local web UI")
        log.warning(
            "kill switch engaged",
            extra={"event": "ui_kill", "outcome": "killed"},
        )
        return build_status(deps)

    @app.get("/", response_class=HTMLResponse)
    def index() -> HTMLResponse:
        return HTMLResponse(render_page(build_status(deps)))

    return app


def render_page(status: dict[str, Any]) -> str:
    """Render the status page.

    Vietnamese **with** diacritics, unlike the CLI: a browser always reads
    UTF-8, while a Windows console code page often is not.

    Every unavailable capability renders its reason, and a control is offered
    only where ``operator_can_act`` says the operator can actually change the
    outcome - a button next to something unfixable is its own dishonesty.
    """
    supervisor = status["supervisor"]
    settings = status["settings"]

    rows: list[str] = []
    for name, entry in status["capabilities"].items():
        if entry["available"]:
            badge = "MOCK" if entry["synthetic"] else "ON"
            css = "mock" if entry["synthetic"] else "on"
            reason = "—"
        else:
            badge = "OFF"
            css = "off"
            reason = _escape(str(entry["blocked_reason"] or ""))
        rows.append(
            f'<tr><td><span class="badge {css}">{badge}</span></td>'
            f"<td><code>{_escape(name)}</code></td><td>{reason}</td></tr>"
        )

    pending = status["pending_decisions"]
    pending_block = (
        '<p class="ok">Không còn quyết định nào đang chờ.</p>'
        if not pending
        else "<ul>"
        + "".join(f"<li><code>{_escape(str(p))}</code></li>" for p in pending)
        + "</ul>"
    )

    blockers = "".join(
        f"<li><code>{_escape(str(b))}</code></li>" for b in status["not_ready_because"]
    )

    model_state = str(supervisor["model_state"])
    model_note = (
        ""
        if not supervisor["model_detail"]
        else f'<p class="muted">{_escape(str(supervisor["model_detail"]))}</p>'
    )
    undecided = (
        ""
        if supervisor["model_state_decided"]
        else '<p class="warn">Trạng thái model chưa xác định — '
        "đang hỏi, chưa có câu trả lời. Không coi là bật.</p>"
    )

    kill_block = (
        ""
        if not supervisor["kill_engaged"]
        else '<p class="danger"><strong>Kill switch đã bật.</strong> '
        f"{_escape(str(supervisor['kill_reason']))}. "
        "Không thể gỡ trong tiến trình này; muốn tiếp tục thì khởi động lại.</p>"
    )

    return f"""<!doctype html>
<html lang="vi"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>MeetAI — supervisor</title>
<style>
 :root {{ color-scheme: light dark; }}
 body {{ font: 15px/1.55 system-ui, sans-serif; max-width: 56rem;
        margin: 2rem auto; padding: 0 1rem; }}
 h1 {{ font-size: 1.3rem; }}
 h2 {{ font-size: 1.05rem; margin-top: 2rem; }}
 table {{ border-collapse: collapse; width: 100%; }}
 td, th {{ padding: .35rem .5rem; border-bottom: 1px solid #8884;
           text-align: left; vertical-align: top; }}
 code {{ font-size: .9em; }}
 .badge {{ display: inline-block; min-width: 3.4rem; text-align: center;
           padding: .1rem .4rem; border-radius: .25rem; font-weight: 600;
           font-size: .78rem; }}
 .badge.on {{ background: #1a7f371f; color: #1a7f37; }}
 .badge.mock {{ background: #9a6b001f; color: #9a6b00; }}
 .badge.off {{ background: #8884; color: inherit; }}
 .banner {{ border: 2px solid #b3261e; padding: .75rem 1rem;
            border-radius: .4rem; }}
 .danger {{ color: #b3261e; font-weight: 600; }}
 .warn {{ color: #9a6b00; }}
 .ok {{ color: #1a7f37; }}
 .muted {{ opacity: .75; }}
 button {{ font: inherit; padding: .4rem .8rem; margin-right: .4rem; }}
</style></head><body>

<h1>MeetAI — supervisor</h1>

<div class="banner">
  <p class="danger">MeetAI chưa sẵn sàng cho cuộc họp thật.</p>
  <p>Lý do:</p>
  <ul>{blockers}</ul>
</div>

<h2>Trạng thái</h2>
<table>
 <tr><td>Supervisor</td><td><code>{_escape(str(supervisor["run_state"]))}</code></td></tr>
 <tr><td>Model</td><td><code>{_escape(model_state)}</code></td></tr>
 <tr><td>Được phép xử lý media</td>
     <td><code>{"có" if supervisor["media_allowed"] else "không"}</code></td></tr>
 <tr><td>Lưu nội dung cuộc họp</td>
     <td><code>{"có" if settings["any_content_persistence_enabled"] else "không"}</code></td></tr>
</table>
{model_note}{undecided}{kill_block}

<h2>Điều khiển</h2>
<p class="muted">“Bắt đầu” chỉ bật các thành phần cục bộ đã được phép — nó
<strong>không</strong> join Discord. “Bật model” <strong>không</strong> bật
audio hay AI bên ngoài.</p>
<div>
  <button onclick="act('/api/start')">Bắt đầu</button>
  <button onclick="act('/api/stop')">Dừng</button>
  <button onclick="act('/api/model/on')">Bật model</button>
  <button onclick="act('/api/model/off')">Tắt model</button>
  <button onclick="if(confirm('Bật kill switch? Không gỡ được trong tiến trình này.')) act('/api/kill')">Kill switch</button>
</div>

<h2>Quyết định đang chờ</h2>
{pending_block}

<h2>Capability</h2>
<table><tr><th>Trạng thái</th><th>Tên</th><th>Lý do nếu OFF</th></tr>
{"".join(rows)}
</table>

<p class="muted">Trang này chỉ hiển thị metadata: trạng thái, số đếm và lý do.
Không có endpoint nào trả về nội dung cuộc họp.</p>

<script>
async function act(path) {{
  const res = await fetch(path, {{
    method: 'POST',
    headers: {{ '{REQUEST_HEADER}': '1' }},
  }});
  if (!res.ok) {{
    const body = await res.json().catch(() => ({{}}));
    alert('Không thực hiện được: ' + (body.detail || res.status));
  }}
  location.reload();
}}
</script>
</body></html>
"""


def _escape(text: str) -> str:
    """Minimal HTML escaping.

    Hand-rolled rather than pulling a template engine: everything rendered
    here is metadata this process produced, and a dependency for four
    replacements would be a dependency the requirement does not need.
    """
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )
