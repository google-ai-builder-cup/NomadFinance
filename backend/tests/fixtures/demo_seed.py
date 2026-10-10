"""Builds the demo workers' Coach and Scam Analyzer seed files (NF-HR-003).

Run from backend/ to write them:   python -m tests.fixtures.demo_seed --write
`tests/unit/test_demo_seed_drift.py` runs the same builders and fails when a committed file differs,
so a change to the plan engine, the score, the scam pipeline or a prompt version is noticed here
and the files are rebuilt, not left to rot.

Nothing is invented by hand that code can work out: the plan runs through the real `CoachPlans`
(score, figures, the checks on the sentences, the translation check) with the sentences of
`demo_seed_plan_text.py` standing in for the model; a scam check runs through the real
`analyze_text` (masking, indicators, the verdict's trimming, the stored document) with the
explanations of `demo_seed_scam_text.py` standing in for the model.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from app.schemas.coach_profile import CoachProfile
from app.schemas.scam import ScamAnalyzeTextRequest
from app.services.scam.analyzer import analyze_text
from tests.fixtures.coach_personas import load_personas
from tests.fixtures.coach_plan_data import (
    UID,
    TranslatingGemini,
    WritingGemini,
    make_plans,
    reach_plan_stage,
)
from tests.fixtures.coach_sessions import NOW
from tests.fixtures.demo_seed_plan_text import plan_text, translation
from tests.fixtures.demo_seed_scam_text import BENIGN, PICKS, SCAM_TYPE, TACTIC_WHY
from tests.fixtures.fake_gemini import FakeGemini
from tests.fixtures.scam_app import FakeTaxonomyRepo
from tests.fixtures.scam_checks import make_store
from tests.fixtures.scam_classify import load_taxonomy
from tests.fixtures.scam_similar import FakeFinder

REPO = Path(__file__).resolve().parents[3]
SEED_DIR = REPO / "data-scripts" / "data" / "seed"
GOLDEN = sorted((REPO / "data-scripts" / "evals").glob("scam_golden_*.jsonl"))
# Any date: the plan's figures do not depend on it. The files hold `@departure` in its place and
# the loader writes the real day (a plan is idempotent on its answers, and the day is one of them).
PLACEHOLDER_DEPARTURE = "2026-11-01"
SESSION_ID = "demo_s_01"
LANGUAGE_NAMES = {"Hindi": "hi", "Tagalog (Filipino)": "tl"}
CONTACT_CHANNEL = {"sms": "sms", "whatsapp": "whatsapp", "email": "email", "social": "other"}


@dataclass(frozen=True)
class Worker:
    stem: str
    uid: str
    language: str
    home: str
    persona_id: str | None = None
    profile: dict[str, Any] | None = None
    rate: tuple[str, float] = ("", 1.0)
    corridor: str | None = None
    departure_in_days: int = 0
    plan_created_days_ago: int = 0
    checkins: dict[str, dict[str, Any]] = field(default_factory=dict)
    comment: str = ""


WORKERS: dict[str, Worker] = {
    "priya_sg_domestic": Worker(
        "priya_sg_domestic",
        "uid_priya_demo",
        "hi",
        "IN",
        persona_id="p03_sg_in_priya",
        corridor="SG-IN",
        departure_in_days=-40,
        plan_created_days_ago=52,
        checkins={
            "d30": {
                "answered_days_after_due": 2,
                "answers": {"remittance": "on_track", "savings": "behind", "pay": "full_on_time"},
            }
        },
        comment="Priya: the Coach persona p03 (SG to India). Left 40 days before the day the "
        "loader runs, so her day 30 check-in is answered.",
    ),
    "rajesh_kr_manufacturing": Worker(
        "rajesh_kr_manufacturing",
        "uid_rajesh_demo",
        "hi",
        "IN",
        profile={
            "destination_country": "KR",
            "job_type": "manufacturing_worker",
            "monthly_salary": {"amount": 1950000.0, "currency": "KRW", "period": "month"},
            "dependents": 2,
            "remittance_target": {"amount": 400000.0, "currency": "KRW", "period": "month"},
            "recruitment_fee_paid": {"amount": 1200000.0, "currency": "KRW", "period": "once"},
            "debt_outstanding": {"amount": 1500000.0, "currency": "KRW", "period": "once"},
            "debt_interest": {"rate_percent": 2.0, "period": "month"},
            "savings": {"amount": 150000.0, "currency": "KRW", "period": "once"},
            "bank_or_wallet": "bank_account",
        },
        rate=("KRW_INR", 0.062),
        corridor=None,
        departure_in_days=21,
        plan_created_days_ago=9,
        comment="Rajesh: Korea to India, no corridor of the six, so no provider is quoted. Leaves "
        "in 21 days: the plan is ready and no check-in is due yet. All amounts in won.",
    ),
    "miguel_jp_care": Worker(
        "miguel_jp_care",
        "uid_miguel_demo",
        "tl",
        "PH",
        persona_id="p10_jp_ph_miguel",
        corridor="JP-PH",
        departure_in_days=-40,
        plan_created_days_ago=55,
        checkins={
            "d30": {
                "answered_days_after_due": 1,
                "answers": {"remittance": "on_track", "savings": "on_track", "pay": "full_on_time"},
            }
        },
        comment="Miguel: the Coach persona p10 (Japan to the Philippines), the high score.",
    ),
}


def iso(value: Any) -> str:
    """JSON for the datetimes of a stored document: UTC, with a Z."""
    if isinstance(value, datetime):
        return value.isoformat().replace("+00:00", "Z")
    raise TypeError(type(value).__name__)


def to_json(document: Any) -> Any:
    return json.loads(json.dumps(document, default=iso, ensure_ascii=False))


def _section(contents: str, tag: str) -> Any:
    found = re.search(rf"<{tag}>\n(.*?)\n</{tag}>", contents, re.DOTALL)
    assert found, tag
    return json.loads(found.group(1))


def _swap(node: Any, old: str, new: str) -> Any:
    if isinstance(node, dict):
        return {k: _swap(v, old, new) for k, v in node.items()}
    if isinstance(node, list):
        return [_swap(v, old, new) for v in node]
    return new if node == old else node


def _persona(worker: Worker) -> SimpleNamespace:
    if worker.persona_id is not None:
        source = {p.id: p for p in load_personas().personas}[worker.persona_id]
        slots = source.expected_slots
        declined = list(source.declined_slots)
        rate = (source.expected_score.rate_pair, source.expected_score.rate)
    else:
        slots = CoachProfile.model_validate({**(worker.profile or {})})
        declined, rate = [], worker.rate
    return SimpleNamespace(
        expected_slots=slots.model_copy(update={"departure_date": PLACEHOLDER_DEPARTURE}),
        declined_slots=declined,
        corridor=worker.corridor,
        expected_score=SimpleNamespace(rate_pair=rate[0], rate=rate[1]),
    )


async def build_coach(worker: Worker) -> dict[str, Any]:
    """The worker's session, plan, translation and check-ins as the backend stores them."""
    persona = _persona(worker)
    captured: dict[str, Any] = {}

    def write(contents: str) -> Any:
        facts = _section(contents, "facts")
        warnings = [(w["id"], w["figures"]) for w in _section(contents, "warnings_to_write")]
        items = [c["id"] for c in _section(contents, "checklist_to_write")]
        captured.update(facts=facts, warnings=warnings, items=items)
        return plan_text("en", facts, warnings, items)

    def translate(contents: str) -> Any:
        found = re.search(r"Translate this plan into (.*?)\.\n", contents)
        assert found
        lang = LANGUAGE_NAMES[found.group(1)]
        return translation(lang, captured["facts"], captured["warnings"], captured["items"])

    plans, _service, session_repo, plan_repo, _ = make_plans(
        persona,
        home=worker.home,
        gemini=WritingGemini(write),
        translator=TranslatingGemini(translate),
    )
    session_id = await reach_plan_stage(_service, persona)
    later = NOW + timedelta(minutes=10)
    result = await plans.create(UID, session_id, "en", later)
    await plans.get(UID, result.response.id, later, worker.language)  # type: ignore[arg-type]

    plan_id = result.response.id
    plan = plan_repo.get(UID, plan_id)
    stored = plan_repo.get_translation(UID, plan_id, worker.language)
    # The harness answers every slot in one turn and in English; the demo worker took the whole
    # interview, in their own language.
    session = {
        **session_repo.docs[(UID, session_id)],
        "language": worker.language,
        "turn_count": 12,
    }
    assert plan is not None and stored is not None
    body: dict[str, Any] = {
        "_comment": worker.comment,
        "uid": worker.uid,
        "language": worker.language,
        "session_id": SESSION_ID,
        "departure_in_days": worker.departure_in_days,
        "plan_created_days_ago": worker.plan_created_days_ago,
        "checkins": worker.checkins,
        "signal_sharing": {"coach": True, "scam": True},
        "session": to_json(session),
        "plan": to_json(plan),
        "translations": {worker.language: to_json(stored)},
    }
    body = _swap(body, PLACEHOLDER_DEPARTURE, "@departure")
    body = _swap(body, session_id, SESSION_ID)
    # These are worked out by the loader from the day it runs; keeping them would be a lie.
    for doc in (body["plan"], body["session"]):
        doc.pop("plan_id", None)
        doc.pop("slot_hash", None)
    body["session"].pop("plan_lock", None)
    return body


# --- the scam checks ---------------------------------------------------------------------


def golden_rows() -> dict[str, dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for path in GOLDEN:
        for line in path.read_text(encoding="utf-8").splitlines():
            if line.strip():
                row = json.loads(line)
                rows[row["id"]] = row
    return rows


def _recordings(row: dict[str, Any], phrases: tuple[str, ...], note: str | None, lang: str) -> Any:
    is_scam = bool(row["is_scam"])
    details = {"contact_channel": CONTACT_CHANNEL.get(row["channel"])}
    classify = {
        "is_scam": is_scam,
        "scam_type": row["scam_type"],
        "tactics": row["tactics"],
        "risk_level": row["risk_level"],
        "confidence": 0.93 if is_scam else 0.9,
        "trigger_phrases": list(phrases),
        "message_language": row["language"],
        "details": details,
    }
    if is_scam:
        text, steps = SCAM_TYPE[row["scam_type"]][lang]
        explain = {
            "why_it_works": [{"tactic": t, "text": TACTIC_WHY[t][lang]} for t in row["tactics"]],
            "scammer_wants": text,
            "next_steps": steps,
        }
        return {
            "scam.classify": {"kind": "structured", "response": classify},
            "scam.explain": {"kind": "structured", "response": explain},
        }
    reassurance, tip = BENIGN[note or ""][lang]
    return {
        "scam.classify": {"kind": "structured", "response": classify},
        "scam.reassure": {
            "kind": "structured",
            "response": {"reassurance": reassurance, "tip": tip},
        },
    }


async def build_scam(worker: Worker) -> dict[str, Any]:
    """The worker's five checks as `analyze_text` stores them, with the day each was made."""
    rows = golden_rows()
    taxonomy = load_taxonomy()
    repo = FakeTaxonomyRepo(taxonomy)
    checks: list[dict[str, Any]] = []
    for n, pick in enumerate(PICKS[worker.stem], start=1):
        row = rows[pick.row_id]
        store = make_store()
        gemini = FakeGemini(_recordings(row, pick.phrases, pick.benign_note, worker.language))
        request = ScamAnalyzeTextRequest(
            text=row["text"], language=worker.language, corridor_id=worker.corridor  # type: ignore[arg-type]
        )
        await analyze_text(
            request, f"seed-{n}", gemini, repo, FakeFinder(), store  # type: ignore[arg-type]
        )
        (document,) = store.checks.docs.values()  # type: ignore[attr-defined]
        document = to_json(document)
        # The loader works the key out from the masked text and the language (as the backend
        # does). It is not kept in the file: a 64-character hex value beside the word `key` is
        # what a secret scanner looks for, and it adds nothing a reader can check.
        for key in ("created_at", "last_checked_at", "expires_at", "reported_at", "cache_key"):
            document.pop(key, None)
        checks.append(
            {
                "id": f"demo_k_{n:02d}",
                "golden_id": pick.row_id,
                "message": row["text"],
                "days_ago": pick.days_ago,
                "hour_utc": pick.hour_utc,
                "document": document,
            }
        )
    return {
        "_comment": f"Five stored checks for {worker.stem}: rows of the reviewed golden sets, "
        "explained in the worker's language. The raw message is here for the drift test only: "
        "the loader writes the masked text.",
        "uid": worker.uid,
        "checks": checks,
    }


def _dump(path: Path, body: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(body, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


async def build_all() -> dict[Path, dict[str, Any]]:
    built: dict[Path, dict[str, Any]] = {}
    for stem, worker in WORKERS.items():
        built[SEED_DIR / "coach" / f"{stem}.json"] = await build_coach(worker)
        built[SEED_DIR / "scam-checks" / f"{stem}.json"] = await build_scam(worker)
    return built


def main() -> int:
    parser = argparse.ArgumentParser(description="Build the NF-HR-003 seed files.")
    parser.add_argument("--write", action="store_true", help="write into data-scripts/data/seed")
    args = parser.parse_args()
    built = asyncio.run(build_all())
    for path, body in built.items():
        if args.write:
            _dump(path, body)
        print(("wrote " if args.write else "built ") + str(path.relative_to(REPO)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
