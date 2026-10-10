"""Workers and reference rows for the load test (NF-HR-007). Emulators only.

Run from backend/ with FIRESTORE_EMULATOR_HOST and FIREBASE_AUTH_EMULATOR_HOST set:

    python -m tests.load.seed --users 60

Creates `load-000` ... with the same password, each onboarded (Singapore, India, English), with
six logged transfers, a Coach plan (the demo plan of Priya, NF-HR-003) and five scam checks, so
every read path of the scenarios finds data. Also writes the two feature flags and the rate
history the trends endpoint reads. It refuses to run without the emulator variables: it must
never write to a real project.
"""

from __future__ import annotations

import argparse
import importlib
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

import firebase_admin
from firebase_admin import auth, firestore

REPO = Path(__file__).resolve().parents[3]
PASSWORD = "load-test-only-password"
PROJECT = "demo-nomadfinance"
AUTH = os.environ.get("FIREBASE_AUTH_EMULATOR_HOST", "")


def uid(n: int) -> str:
    return f"load-{n:03d}"


def email(n: int) -> str:
    return f"{uid(n)}@load.example"


def create_account(app: firebase_admin.App, n: int) -> None:
    """The account, with the uid and password the load test signs in with. A second run leaves
    an existing one as it is."""
    try:
        auth.create_user(uid=uid(n), email=email(n), password=PASSWORD, app=app)
    except auth.UidAlreadyExistsError:
        pass


def _demo_documents(now: datetime) -> tuple[Any, Any, Any]:
    sys.path.insert(0, str(REPO / "data-scripts"))
    coach = importlib.import_module("src.loaders.demo_coach")
    scam = importlib.import_module("src.loaders.demo_scam")
    plan_seed = importlib.import_module("src.validators.demo_coach").load(
        REPO / "data-scripts/data/seed/coach/priya_sg_domestic.json"
    )
    scam_seed = importlib.import_module("src.validators.demo_scam").load(
        REPO / "data-scripts/data/seed/scam-checks/priya_sg_domestic.json"
    )
    return coach.build_documents(plan_seed, now), scam, scam_seed


def main() -> int:
    parser = argparse.ArgumentParser(description="Seed the load-test workers (emulators only).")
    parser.add_argument("--users", type=int, default=60)
    args = parser.parse_args()
    if not (os.environ.get("FIRESTORE_EMULATOR_HOST") and AUTH):
        print("Set FIRESTORE_EMULATOR_HOST and FIREBASE_AUTH_EMULATOR_HOST: emulators only.")
        return 1

    app = firebase_admin.initialize_app(options={"projectId": PROJECT})
    db = firestore.client(app)
    now = datetime.now(UTC)
    plan, scam_loader, scam_seed = _demo_documents(now)

    db.collection("config").document("feature_flags").set(
        {
            "flags": {
                "coach": {"enabled": True, "allow_uids": []},
                "scam": {"enabled": True, "allow_uids": []},
            }
        }
    )
    for pair, rate in {
        "SGD_PHP": 42.0,
        "SGD_INR": 62.0,
        "AUD_INR": 54.0,
        "MYR_IDR": 3700.0,
        "JPY_PHP": 0.38,
        "AUD_PHP": 37.0,
    }.items():
        db.collection("rates_cache").document(pair).set(
            {
                "rate": rate,
                "provider": "frankfurter",
                "rate_date": now.date().isoformat(),
                "fetched_at": now,
            }
        )
        daily = {
            (now.date() - timedelta(days=d)).isoformat(): {
                "rate": round(rate * (1 + 0.002 * ((d % 7) - 3)), 4),
                "provider": "frankfurter",
                "source": "backfill",
            }
            for d in range(1, 120)
        }
        db.collection("rates_history").document(pair).set({"daily": daily, "pair": pair})

    for n in range(args.users):
        create_account(app, n)
        user = db.collection("users").document(uid(n))
        user.set(
            {
                "preferred_language": "en",
                "host_country": "SG",
                "home_country": "IN",
                "job_type": "domestic_worker",
                "onboarding_completed_at": now,
                "created_at": now,
                "updated_at": now,
                "schema_version": 1,
                "signal_sharing": {"coach": True, "scam": True},
            }
        )
        batch = db.batch()
        for t in range(6):
            day = (now.date() - timedelta(days=30 * t + 3)).isoformat()
            batch.set(
                user.collection("transfers").document(f"t{t}"),
                {
                    "entry_date": day,
                    "corridor_id": "SG-IN",
                    "provider_name": "Wise",
                    "send_amount": 400.0,
                    "send_currency": "SGD",
                    "receive_amount": 25000.0,
                    "receive_currency": "INR",
                    "fee": 3.5,
                    "cost_pct": 1.4,
                    "source": "remittance_log",
                    "created_at": now,
                    "updated_at": now,
                    "schema_version": 1,
                },
            )
        batch.set(user.collection("coach_sessions").document(plan.session_id), plan.session)
        batch.set(user.collection("coach_plans").document(plan.plan_id), plan.plan)
        for lang, doc in plan.translations.items():
            batch.set(
                user.collection("coach_plans")
                .document(plan.plan_id)
                .collection("translations")
                .document(lang),
                doc,
            )
        for check in scam_seed.checks:
            document = scam_loader.check_document(check, now, None)
            batch.set(
                user.collection("scam_checks").document(scam_loader.check_id(document)), document
            )
        batch.commit()
    print(f"seeded {args.users} workers; plan {plan.plan_id}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
