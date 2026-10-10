"""Replay the twelve Coach personas through the real endpoints (NF-FC-024).

Run from backend/:  python -m tests.regression.run_coach_regression --base-url https://...

Each persona gets a new session, types its scripted messages in order, confirms the review and
asks for the plan. The run checks the turn count, the stored slots, the score band and that the
plan was stored (the server stores none that fails its figure and sentence checks). It calls the
live Gemini models through the server, so it needs an account the `coach` flag is on for.

The Firebase ID token of that account is read from COACH_EVAL_ID_TOKEN, never from an option, so
it does not end up in a shell history or a process list. The token must last the whole run
(about 20 minutes at the default pace; an ID token lasts an hour).

  --base-url URL     the server (default COACH_EVAL_BASE_URL, else http://127.0.0.1:8080)
  --only ID          run only this persona (repeatable); a partial run writes no report
  --report PATH      write the report here (default docs/evals/coach-regression-<date>.md)
  --usage-log PATH   a Cloud Logging export of the run's gemini_call lines, for token usage
  --rpm N            Gemini-spending calls a minute (default 9; the server allows 10 a worker)
  --plan-language L  language of the plan and its PDF (default en)

Exit code: 0 every persona passed; 1 at least one failed (the report is written either way);
2 the run could not start or the setup is wrong (no token, no access, no server).
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

import httpx

from tests.fixtures.coach_personas import Persona, load_personas
from tests.regression.coach_client import CoachApi, SetupError
from tests.regression.coach_replay import PersonaResult, replay_persona
from tests.regression.coach_report import RunInfo, parse_usage_log, render_report, uid_hash_of

REPORT_DIR = Path(__file__).resolve().parents[3] / "docs" / "evals"
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
NOT_RUN = 2
LANGUAGES = ("en", "hi", "tl", "id", "ne", "bn")


def check_address(base_url: str) -> None:
    """A bearer token goes only over https, or to this machine.

    Raises:
        SetupError: The address is not one of those.
    """
    parts = urlsplit(base_url)
    if parts.scheme != "https" and parts.hostname not in LOCAL_HOSTS:
        raise SetupError(
            f"{base_url} is not https and not this machine: the token would travel in clear"
        )


def _show(result: PersonaResult) -> None:
    mark = "ok    " if result.passed else "FAILED"
    print(
        f"{mark} {result.persona.id}  "
        f"turns {result.turn_count}/{result.persona.expected_turn_count}"
        f"  band {result.band}  {result.seconds:.0f} s",
        flush=True,
    )
    for problem in result.problems:
        print(f"         {problem}", flush=True)


async def run(
    api: CoachApi, personas: list[Persona], today: datetime, plan_language: str
) -> list[PersonaResult]:
    """One persona after another: a worker has one active session, and one turn budget."""
    results: list[PersonaResult] = []
    for persona in personas:
        result = await replay_persona(api, persona, today.date(), plan_language)
        _show(result)
        results.append(result)
    return results


def main(argv: list[str] | None = None, transport: httpx.AsyncBaseTransport | None = None) -> int:
    parser = argparse.ArgumentParser(description="Replay the Coach personas through the endpoints.")
    parser.add_argument(
        "--base-url", default=os.environ.get("COACH_EVAL_BASE_URL", "http://127.0.0.1:8080")
    )
    parser.add_argument("--only", action="append", default=[], metavar="ID")
    parser.add_argument("--report", type=Path)
    parser.add_argument("--usage-log", type=Path)
    parser.add_argument("--rpm", type=int, default=9)
    parser.add_argument("--plan-language", default="en", choices=LANGUAGES)
    args = parser.parse_args(argv)
    if args.rpm < 0:
        parser.error("--rpm cannot be negative")
    if reconfigure := getattr(sys.stdout, "reconfigure", None):
        reconfigure(encoding="utf-8")

    file = load_personas()
    unknown = sorted(set(args.only) - {p.id for p in file.personas})
    if unknown:
        parser.error(f"no such persona: {', '.join(unknown)}")
    personas = [p for p in file.personas if not args.only or p.id in args.only]
    token = os.environ.get("COACH_EVAL_ID_TOKEN", "").strip()
    try:
        if not token:
            raise SetupError(
                "COACH_EVAL_ID_TOKEN is not set: put the test account's ID token in it"
            )
        check_address(args.base_url)
        usage = (
            parse_usage_log(args.usage_log.read_text(encoding="utf-8")) if args.usage_log else None
        )
    except (SetupError, OSError, ValueError) as exc:
        print(f"FAIL {exc}")
        return NOT_RUN

    started = datetime.now(UTC)
    api = CoachApi(args.base_url, token, rpm=args.rpm, transport=transport)
    print(
        f"{len(personas)} persona(s) against {args.base_url}, "
        f"at most {args.rpm or 'any'} calls a minute"
    )
    try:
        results = asyncio.run(_run_and_close(api, personas, started, args.plan_language))
    except SetupError as exc:
        print(f"FAIL {exc}")
        return NOT_RUN

    passed = sum(1 for r in results if r.passed)
    print(f"\n{passed} / {len(results)} personas passed")
    info = RunInfo(
        when=started,
        base_url=args.base_url,
        rpm=args.rpm,
        plan_language=args.plan_language,
        personas_version=file.version,
        rubric_version=file.rubric_version,
        uid_hash=uid_hash_of(token),
    )
    path: Path | None = args.report or (
        None if args.only else REPORT_DIR / f"coach-regression-{started:%Y-%m-%d}.md"
    )
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(render_report(results, info, usage).encode("utf-8"))
        print(f"Report: {path}")
    else:
        print("Partial run: no report written (give --report to keep one).")
    return 0 if passed == len(results) else 1


async def _run_and_close(
    api: CoachApi, personas: list[Persona], started: datetime, plan_language: str
) -> list[PersonaResult]:
    try:
        return await run(api, personas, started, plan_language)
    finally:
        await api.aclose()


if __name__ == "__main__":
    sys.exit(main())
