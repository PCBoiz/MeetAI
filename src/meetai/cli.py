"""Command-line entry point for the MeetAI supervisor.

Phase 0 scope: validate configuration and report what MeetAI can and cannot
do. It deliberately refuses to imply readiness it does not have - the session
lifecycle and every platform adapter are later slices.

``dry-run`` is the one command that exercises the response boundary. It is a
**local** demonstration against an in-memory sink: no media, no network, no
persistence, no model. It is not a meeting test and the report it prints says
so in its own output, because a command named "run" is the easiest thing in
this repository to mistake for readiness.

No failure path prints a raw exception. ``str(ValidationError)`` embeds the
offending input, and for a model-level error that input is the whole
configuration mapping, so printing it verbatim would put the tail of a
credential on stderr. Everything goes through
:func:`meetai.settings.sanitised_validation_errors` or reports a type name.
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from collections.abc import Sequence

from pydantic import ValidationError

from meetai import __version__
from meetai.capabilities import CapabilityReport, current_capabilities
from meetai.errors import MeetAIError
from meetai.logging_setup import configure_logging, get_logger
from meetai.settings import Settings, load_settings, sanitised_validation_errors

EXIT_OK = 0
EXIT_CONFIG_INVALID = 2
EXIT_UI_UNAVAILABLE = 3
EXIT_UI_BIND_FAILED = 4
EXIT_DRYRUN_UNEXPECTED = 5


def _status_report(
    settings: Settings, capabilities: CapabilityReport
) -> dict[str, object]:
    """Assemble the status report.

    Every entry is a fact about this build, not an aspiration. The capability
    list comes from :mod:`meetai.capabilities`, which refuses to hold an
    unavailable capability without a reason, so this function cannot
    accidentally render an unexplained ``OFF``.
    """
    return {
        "version": __version__,
        # Phase 0 is complete; several Phase 1 slices are too. Reported as a
        # range rather than a single number, because claiming "0" understates
        # what the build does and claiming "1" overstates it.
        "phase": "0 complete, 1 in progress",
        "capabilities": capabilities.as_dict(),
        "settings": settings.redacted_summary(),
    }


def _render_human(report: dict[str, object]) -> str:
    """Human-readable status.

    Vietnamese without diacritics: a Windows console's code page is often not
    UTF-8, and a status display that renders as mojibake is worse than a plain
    one. The web UI (slice S0.6) will use full Vietnamese.
    """
    capabilities = report["capabilities"]
    settings = report["settings"]
    if not isinstance(capabilities, dict) or not isinstance(settings, dict):
        raise TypeError("report shape khong dung")

    lines = [
        f"MeetAI {report['version']} - Phase {report['phase']}",
        "",
        "Kha nang (capability):",
    ]
    for name, info in capabilities.items():
        mark = "ON " if info["available"] else "OFF"
        if info["available"] and info["synthetic"]:
            mark = "MOCK"
        suffix = f"  <- {info['blocked_reason']}" if info["blocked_reason"] else ""
        lines.append(f"  [{mark}] {name}{suffix}")

    lines += [
        "",
        "Cau hinh (da loc bo secret):",
        f"  consent_mode          : {settings['consent_mode']}",
        f"  late_join_policy      : {settings['late_join_policy']}",
        f"  xu ly media duoc phep : "
        f"{'CO' if settings['media_processing_allowed'] else 'KHONG'}",
        f"  luu noi dung cuoc hop : "
        f"{'CO' if settings['any_content_persistence_enabled'] else 'KHONG'}",
        f"  discord token         : "
        f"{'da cau hinh' if settings['discord_bot_token_configured'] else 'chua co'}",
    ]

    pending = settings["pending_decisions"]
    if pending:
        lines += [
            "",
            "Cho chu du an quyet dinh (chua the bat tinh nang lien quan):",
            *(f"  - {name}" for name in pending),
        ]

    # A tripwire can only be True on an instance built through a path that
    # skipped validation. Saying so loudly beats rendering a status report that
    # looks identical to a safe one.
    if settings["requested_external_ai"] or settings["requested_live_discord_voice"]:
        lines += [
            "",
            "CANH BAO: tripwire dang bat. Doi tuong Settings nay khong qua validation.",
        ]
    return "\n".join(lines)


def _print_config_failure(messages: Sequence[str]) -> None:
    """Report a refused configuration. Messages are already value-free."""
    print("Cau hinh khong hop le, MeetAI khong khoi dong:", file=sys.stderr)
    for message in messages:
        print(f"  - {message}", file=sys.stderr)


def main(argv: Sequence[str] | None = None) -> int:
    """Run the CLI. Returns a process exit code."""
    parser = argparse.ArgumentParser(
        prog="meetai",
        description="MeetAI supervisor (Phase 0: config validation and status only)",
    )
    parser.add_argument(
        "command",
        choices=["status", "serve", "dry-run"],
        help=(
            "status: validate configuration and print the capability report. "
            "serve: run the local web UI on loopback. "
            "dry-run: push synthetic cases through the response boundary into "
            "an in-memory sink (no media, no network, no persistence)"
        ),
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the report as JSON instead of human-readable text",
    )
    parser.add_argument(
        "--log-level",
        default="WARNING",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="verbosity of the metadata-only log on stderr (default: WARNING)",
    )
    args = parser.parse_args(argv)

    configure_logging(level=getattr(logging, args.log_level))
    log = get_logger("cli")

    try:
        settings = load_settings()
    except ValidationError as exc:
        # Never `print(exc)`: pydantic embeds the raw input, which for a
        # model-level error is the entire configuration mapping.
        _print_config_failure(sanitised_validation_errors(exc))
        # log.error, not log.exception: attaching exc_info would hand the
        # filter an exception whose payload holds the raw input mapping. The
        # filter sanitises it, but not attaching it is the stronger choice.
        log.error(  # noqa: TRY400
            "configuration rejected", extra={"reason_code": "validation_error"}
        )
        return EXIT_CONFIG_INVALID
    except MeetAIError as exc:
        # These messages are written to be value-free (see meetai.errors).
        _print_config_failure([str(exc)])
        log.error(  # noqa: TRY400 - see the sibling handler above
            "configuration rejected",
            extra={"reason_code": type(exc).__name__},
        )
        return EXIT_CONFIG_INVALID

    settings.assert_tripwires_disarmed()

    if args.command == "serve":
        return _serve(settings, log)

    if args.command == "dry-run":
        return _dry_run(log, as_json=args.json)

    report = _status_report(settings, current_capabilities())
    if args.json:
        print(json.dumps(report, indent=2, ensure_ascii=False))
    else:
        print(_render_human(report))

    log.info(
        "status reported",
        extra={
            "event": "status",
            "outcome": "ok",
            # Whether media may be processed is a state, not content.
            "state": "media_allowed"
            if settings.media_processing_allowed
            else "media_blocked",
        },
    )
    return EXIT_OK


def _dry_run(log: logging.Logger, *, as_json: bool) -> int:
    """Run the level-2 dry-run and report it.

    Deliberately does **not** consult ``settings``, and that is not an
    oversight: this path touches no media, so gating it on
    ``media_processing_allowed`` would imply it is a media path and teach the
    operator that the consent gate is the thing standing between them and a
    meeting. What stands between them and a meeting is that no sink exists.

    A deviation from the written expectations exits non-zero. The dry-run is a
    demonstration, but it is also a check, and a check whose failure exits 0
    is a check nobody notices.
    """
    from meetai.dryrun import emitted_count, report, run
    from meetai.dryrun import main as run_dry_run

    if as_json:
        results, sink = run()
        findings = report(results, emitted=emitted_count(sink))
        print(json.dumps(findings, indent=2, ensure_ascii=False))
        unexpected = findings["unexpected"]
        ok = not (isinstance(unexpected, list) and unexpected)
    else:
        rendered, ok = run_dry_run()
        print(rendered)

    log.info(
        "dry-run completed",
        extra={
            "event": "dry_run",
            "outcome": "ok" if ok else "unexpected",
            # The level, not a readiness claim. A log reader must not be able
            # to mistake this line for evidence of an integration.
            "state": "level_2_recording_sink",
        },
    )
    return EXIT_OK if ok else EXIT_DRYRUN_UNEXPECTED


def _serve(settings: Settings, log: logging.Logger) -> int:
    """Run the local web UI.

    Configuration is already validated by the time this is called - that
    ordering is the whole value of the egress guard, since a guard that runs
    after the socket is bound is decoration.

    A bind failure is a hard refusal with a non-zero exit, and the port is
    never retried on a different number. The operator's bookmark is the trust
    anchor: silently moving the UI to another port is the port-squatting attack
    performed by yourself.
    """
    try:
        import uvicorn

        from meetai.supervisor import ModelSwitch, Supervisor
        from meetai.ui import UiDependencies, create_app
    except ImportError as exc:
        print(
            "Local web UI can extra 'ui'. Chay: uv sync --extra ui",
            file=sys.stderr,
        )
        # log.error, not log.exception: see the configuration handlers above.
        log.error(  # noqa: TRY400
            "ui extra missing", extra={"reason_code": type(exc).__name__}
        )
        return EXIT_UI_UNAVAILABLE

    supervisor = Supervisor(
        settings_allows_media=lambda: settings.media_processing_allowed,
        # No loader: there is no model runtime yet, and a mock reporting READY
        # would be the exact false claim the capability report forbids.
        model=ModelSwitch(),
    )
    app = create_app(UiDependencies(settings=settings, supervisor=supervisor))

    print(
        f"MeetAI supervisor UI: http://{settings.ui_host}:{settings.ui_port}",
        file=sys.stderr,
    )
    print(
        "MeetAI CHUA san sang cho cuoc hop that. Mo trang de xem ly do.",
        file=sys.stderr,
    )
    try:
        uvicorn.run(
            app,
            host=settings.ui_host,
            port=settings.ui_port,
            log_config=None,  # keep MeetAI's metadata-only logging
            access_log=False,  # access logs carry paths and query strings
        )
    except (OSError, SystemExit) as exc:
        # SystemExit, not just OSError, and that is measured rather than
        # assumed: uvicorn catches the bind error itself, logs it, and calls
        # sys.exit(3). An `except OSError` here never fired, and the process
        # exited 3 - which collides with EXIT_UI_UNAVAILABLE, so a squatted
        # port would have been reported to the operator as "the ui extra is
        # missing". Catching SystemExit puts the exit code back under our
        # control.
        print(
            f"Khong bind duoc cong {settings.ui_port}: {type(exc).__name__}. "
            "UI KHONG khoi dong. Khong tu doi sang cong khac - bookmark cua ban "
            "la neo tin cay, va tu y doi cong la chinh cuoc tan cong chiem cong "
            "do ban tu thuc hien.",
            file=sys.stderr,
        )
        log.error(  # noqa: TRY400 - see the configuration handlers above
            "ui bind failed",
            extra={"reason_code": type(exc).__name__, "outcome": "refused"},
        )
        return EXIT_UI_BIND_FAILED
    return EXIT_OK


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
