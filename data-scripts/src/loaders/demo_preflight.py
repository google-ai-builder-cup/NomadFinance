"""Check that a project can run the finale demo from a cold account (NF-HR-003). Read-only.

Run from data-scripts/:  python -m src.loaders.demo_preflight
The finale is one worker's journey: the Coach, Contract Shield, the Scam Analyzer, a report to the
Radar. Each step reads reference data that the demo seed does not write, and a step that finds
none fails for a worker with an empty account just as it does for a seeded one. This lists, for
the project the loaders point at, what is there and what is not, with the command that fixes each
gap. Nothing is written. Exit code 0: everything required is in place (warnings are about
freshness or things only an operator can switch on); 1: something required is missing.
"""

from __future__ import annotations

import argparse
import logging
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any, Literal

from google.api_core.exceptions import GoogleAPICallError
from google.cloud.firestore import Client
from google.cloud.firestore_v1.base_query import FieldFilter

from src.firestore_client import get_firestore_client

log = logging.getLogger(__name__)

HOSTS = ("SG", "KR", "MY", "JP", "HK", "AU")
RATE_PAIRS = ("SGD_PHP", "SGD_INR", "AUD_INR", "MYR_IDR", "JPY_PHP", "AUD_PHP")
DEMO_UIDS = ("uid_priya_demo", "uid_rajesh_demo", "uid_miguel_demo")
MODULE_FLAGS = ("coach", "scam")
MIN_PATTERNS = 480  # 60 for each of the 8 scam types (NF-SA-006)
MIN_TAXONOMY = 14  # 8 types and 6 tactics (NF-SA-001), without `_meta`
RATES_FRESH_FOR = timedelta(hours=48)
Status = Literal["ok", "warn", "fail"]


@dataclass(frozen=True)
class Item:
    name: str
    status: Status
    detail: str
    fix: str = ""


def count(reference: Any) -> int:
    """How many documents a collection holds: the server's count where there is one."""
    try:
        return int(reference.count().get()[0][0].value)
    except (AttributeError, GoogleAPICallError, NotImplementedError, IndexError):
        return sum(1 for _ in reference.select([]).stream())


def _exists(client: Client, path: str) -> bool:
    return bool(client.document(path).get().exists)


def _all_present(client: Client, collection: str, ids: tuple[str, ...]) -> list[str]:
    return [i for i in ids if not _exists(client, f"{collection}/{i}")]


def reference_data(client: Client, now: datetime) -> list[Item]:
    items: list[Item] = []

    def need(name: str, missing: list[str], fix: str, found: str) -> None:
        if missing:
            items.append(Item(name, "fail", "missing: " + ", ".join(missing), fix))
        else:
            items.append(Item(name, "ok", found))

    need(
        "corridors",
        _all_present(client, "corridors", ("SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH")),
        "python -m src.loaders.corridors",
        "6 corridors",
    )
    need(
        "labor laws",
        _all_present(client, "labor_laws", HOSTS),
        "python -m src.loaders.ilo_natlex",
        "6 countries",
    )
    need(
        "cost baselines (the Coach score and plan)",
        _all_present(client, "cost_baselines", HOSTS),
        "python -m src.loaders.cost_baselines   (D-216: not loaded in production)",
        "6 countries",
    )
    need(
        "complaint templates",
        _all_present(client, "complaint_templates", HOSTS),
        "python -m src.loaders.complaint_templates",
        "6 countries",
    )

    missing_pairs = _all_present(client, "rates_cache", RATE_PAIRS)
    if missing_pairs:
        items.append(
            Item(
                "exchange rates",
                "fail",
                "missing: " + ", ".join(missing_pairs),
                "gcloud scheduler jobs run refresh-rates --location asia-south1",
            )
        )
    else:
        fetched = [
            (client.document(f"rates_cache/{p}").get().to_dict() or {}).get("fetched_at", now)
            for p in RATE_PAIRS
        ]
        oldest = min(t for t in fetched if isinstance(t, datetime)) if fetched else now
        stale = isinstance(oldest, datetime) and now - oldest > RATES_FRESH_FOR
        items.append(
            Item(
                "exchange rates",
                "warn" if stale else "ok",
                (
                    f"oldest {oldest:%Y-%m-%d %H:%M} UTC"
                    if isinstance(oldest, datetime)
                    else "6 pairs"
                ),
                "gcloud scheduler jobs run refresh-rates --location asia-south1" if stale else "",
            )
        )

    types = count(client.collection("scam_taxonomy")) - int(_exists(client, "scam_taxonomy/_meta"))
    items.append(
        Item(
            "scam taxonomy",
            "ok" if types >= MIN_TAXONOMY and _exists(client, "scam_taxonomy/_meta") else "fail",
            f"{types} types and tactics",
            "python -m src.loaders.scam_taxonomy",
        )
    )
    patterns = count(client.collection("scam_patterns"))
    items.append(
        Item(
            "scam patterns (needs an embedding key)",
            "ok" if patterns >= MIN_PATTERNS else "fail",
            f"{patterns} of {MIN_PATTERNS}",
            "python -m src.loaders.scam_patterns   (GEMINI_API_KEY)",
        )
    )
    return items


def module_flags(client: Client) -> list[Item]:
    snapshot = client.document("config/feature_flags").get()
    flags = ((snapshot.to_dict() or {}).get("flags") or {}) if snapshot.exists else {}
    items = []
    for name in MODULE_FLAGS:
        entry = flags.get(name) or {}
        on_for_all = entry.get("enabled") is True
        allowed = set(entry.get("allow_uids") or [])
        if on_for_all:
            items.append(Item(f"flag {name}", "ok", "on for everyone"))
        elif set(DEMO_UIDS) <= allowed:
            items.append(Item(f"flag {name}", "ok", "on for the three demo workers"))
        else:
            items.append(
                Item(
                    f"flag {name}",
                    "fail",
                    "off for the demo workers",
                    f"set config/feature_flags.flags.{name}.enabled to true (an operator step)",
                )
            )
    return items


def demo_workers(client: Client) -> list[Item]:
    items = []
    for uid in DEMO_UIDS:
        user = client.collection("users").document(uid)
        if not user.get().exists:
            items.append(Item(uid, "fail", "no user document", "python -m src.loaders.seed"))
            continue
        plans = sum(
            1
            for _ in user.collection("coach_plans")
            .where(filter=FieldFilter("demo_seed", "==", True))
            .stream()
        )
        checks = sum(
            1
            for _ in user.collection("scam_checks")
            .where(filter=FieldFilter("demo_seed", "==", True))
            .stream()
        )
        entries = count(user.collection("income"))
        problems = []
        if entries == 0:
            problems.append("no money history (python -m src.loaders.seed)")
        if plans == 0:
            problems.append("no Coach plan (python -m src.loaders.demo_coach)")
        if checks != 5:
            problems.append(f"{checks} of 5 scam checks (python -m src.loaders.demo_scam)")
        items.append(
            Item(
                uid,
                "fail" if problems else "ok",
                "; ".join(problems) or f"history, {plans} plan, {checks} scam checks",
            )
        )
    return items


def run(client: Client, now: datetime) -> list[Item]:
    return [*reference_data(client, now), *module_flags(client), *demo_workers(client)]


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description="Check the project can run the finale demo.").parse_args(
        argv
    )
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    items = run(get_firestore_client(), datetime.now(UTC))
    marks = {"ok": "ok  ", "warn": "warn", "fail": "FAIL"}
    for item in items:
        log.info("%s  %s: %s", marks[item.status], item.name, item.detail)
        if item.fix and item.status != "ok":
            log.info("        fix: %s", item.fix)
    failed = [i for i in items if i.status == "fail"]
    if failed:
        log.info("%d required item(s) missing", len(failed))
        return 1
    log.info("ready for the demo")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
