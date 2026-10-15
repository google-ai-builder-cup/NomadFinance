"""Project a demo day's Gemini requests per model against each model's daily limit (NF-HR-010).

    python scripts/project_demo_usage.py                      # the plan in the runbook
    python scripts/project_demo_usage.py --visitors 15 --coach-reply-tier extraction
    python scripts/project_demo_usage.py --rpd reasoning=500 --rpd classification=1500

Each journey (one Coach interview, one scam check, ...) is a list of Gemini operations with the
tier they run on and how many times, from the code and from measurements, each noted below;
`tests/integration/api/test_gemini_journey_counts.py` runs the real services against a counting
fake and fails if a table row here stops matching the code. A scenario says how many journeys the
day holds. The result is requests per model, as a share of the model's requests per day.

The daily limits come from `--rpd`, else from `infra/monitoring/quota-limits.json` once someone has
read them in Google AI Studio (D-122), else from the original design's figures (500 for the
reasoning tier, 1,500 for each of the others), which names models that no longer exist: those rows
are marked ASSUMED, and a run that used any of them proves nothing about the real project.

Exit code 0 when every model is at or under the target (default 60 %), 1 when one is over, 2 for
bad arguments. A model with no limit at all is reported and does not fail the run.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path

TIERS = ("reasoning", "extraction", "classification", "embedding")
DESIGN_DOC_RPD = {"reasoning": 500, "extraction": 1500, "classification": 1500, "embedding": 1500}
LIMITS_FILE = Path(__file__).resolve().parents[2] / "infra" / "monitoring" / "quota-limits.json"

# Retries (a 503 or a per-minute 429 is tried again, and every attempt counts) and the odd call
# the table does not name. A guess, kept in one place.
OVERHEAD = 1.10

# The text turns of one persona's interview, averaged over the 12 personas (the length of each
# `script` in tests/fixtures/coach_personas.json, which a test checks).
INTERVIEW_TURNS = 11.67


@dataclass(frozen=True)
class Step:
    operation: str
    tier: str
    count: float


def journeys(coach_reply_tier: str) -> dict[str, list[Step]]:
    """Requests to Gemini per journey. `coach_reply_tier` is where the coach's reply is sent."""
    turns = INTERVIEW_TURNS
    return {
        # The coach speaks first (1 reply), then each text turn is read (extract; the last, at the
        # review, is read by coach.review instead) and answered (reply). The guard asks the model
        # about 3 of 140 persona messages. A summary is made once the history window is passed
        # (only the 14-turn persona). The plan is one call, and 1 in 3 first answers was rejected
        # in live runs (D-220). Eight of the 12 personas read the plan in another language.
        "coach_interview": [
            Step("coach.reply", coach_reply_tier, 1 + turns),
            Step("coach.extract", "classification", turns - 1),
            Step("coach.review", "classification", 1),
            Step("coach.guard", "classification", round(turns * 3 / 140, 2)),
            Step("coach.summarise", "classification", 0.3),
            Step("coach.plan", "reasoning", 1.33),
            Step("coach.translate_plan", "classification", 0.8),
        ],
        # A new message: the verdict, the nearest known scams (one embedding), and the explainer
        # (the reasoning tier for a scam, a reassurance on the fast tier for a message that is not).
        "scam_check_scam": [
            Step("scam.classify", "classification", 1),
            Step("scam.embed", "embedding", 1),
            Step("scam.explain", "reasoning", 1),
        ],
        "scam_check_benign": [
            Step("scam.classify", "classification", 1),
            Step("scam.embed", "embedding", 1),
            Step("scam.reassure", "classification", 1),
        ],
        "scam_screenshot_extra": [Step("scam.read_screenshot", "extraction", 1)],
        # Detect and read the document, compare it with the law, write the complaint letter (one
        # call for both copies, only when a clause is dangerous) and translate the report (the
        # two thirds of workers who do not read English).
        "contract_analysis": [
            Step("contract.detect", "extraction", 1),
            Step("contract.extract", "extraction", 1),
            Step("contract.compare", "reasoning", 1),
            Step("contract.complaint", "reasoning", 1),
            Step("contract.translate", "classification", 0.67),
        ],
        "radar_report": [
            Step("radar.extract_entity", "extraction", 1),
            Step("radar.validate", "classification", 1),
            Step("radar.categorize", "classification", 1),
            Step("radar.embed", "embedding", 1),
            # A new alert is written in each worker's language (up to six); one report in three
            # tips a corridor over the alert threshold.
            Step("radar.alert_notification", "classification", 2),
        ],
        "remittance_recommend": [Step("remittance.recommend", "classification", 1)],
        # A bill read, the entries sorted into categories, and the profile's narrative (the
        # weekly job; run by hand once per demo worker).
        "fib_session": [
            Step("fib.extract_bill", "extraction", 1),
            Step("fib.categorize", "classification", 1),
            Step("fib.synthesize_narrative", "reasoning", 1),
        ],
    }


@dataclass(frozen=True)
class Scenario:
    rehearsals: int = 3
    live_runs: int = 1
    visitors: int = 30
    # A team run is one worker journey: Coach, Contract Shield, three scam checks (two scams, one
    # message that is not), a Radar report, two remittance comparisons, a Financial Identity update.
    prewarmed_team_scam_checks: bool = True  # NF-HR-003 seeds them, so a re-check is a cache hit
    visitor_contract_share: float = 0.5
    visitor_screenshot_share: float = 0.1
    recommend_hit_rate: float = 0.5  # the demo compares the same corridor and amount again
    coach_reply_tier: str = "classification"

    def counts(self) -> dict[str, float]:
        team = self.rehearsals + self.live_runs
        v = self.visitors
        team_checks = 0 if self.prewarmed_team_scam_checks else team
        return {
            "coach_interview": team + v,
            "scam_check_scam": 2 * (team_checks + v),
            "scam_check_benign": team_checks + v,
            "scam_screenshot_extra": v * 3 * self.visitor_screenshot_share,
            "contract_analysis": team + v * self.visitor_contract_share,
            "radar_report": team,
            "remittance_recommend": (2 * team + v) * (1 - self.recommend_hit_rate),
            "fib_session": team,
        }


def project(scenario: Scenario) -> dict[tuple[str, str], float]:
    """Requests per (feature, tier) for the day, retries included."""
    table = journeys(scenario.coach_reply_tier)
    totals: dict[tuple[str, str], float] = defaultdict(float)
    for name, times in scenario.counts().items():
        for step in table[name]:
            totals[(step.operation.split(".", 1)[0], step.tier)] += times * step.count * OVERHEAD
    return dict(totals)


def read_rpd(overrides: dict[str, int]) -> tuple[dict[str, int], set[str]]:
    """The daily limit per tier, and the tiers whose figure is only the original design's."""
    limits = json.loads(LIMITS_FILE.read_text(encoding="utf-8"))
    from_file = {
        entry["tier"].lower(): entry["rpd"]
        for entry in limits["models"].values()
        if entry["rpd"] is not None
    }
    rpd: dict[str, int] = {}
    assumed: set[str] = set()
    for tier in TIERS:
        if tier in overrides:
            rpd[tier] = overrides[tier]
        elif tier in from_file:
            rpd[tier] = from_file[tier]
        else:
            rpd[tier] = DESIGN_DOC_RPD[tier]
            assumed.add(tier)
    return rpd, assumed


def shares_by_tier() -> dict[str, dict[str, float]]:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from app.integrations.gemini.budget import SHARES

    return SHARES


def report(scenario: Scenario, rpd: dict[str, int], assumed: set[str], target: float) -> int:
    totals = project(scenario)
    shares = shares_by_tier()
    per_tier = {tier: sum(n for (_, t), n in totals.items() if t == tier) for tier in TIERS}
    print(f"Scenario: {scenario}")
    print(f"Retry overhead x{OVERHEAD}; target {target:.0%} of each model's day\n")
    print(f"{'tier':<15}{'requests':>9}{'daily limit':>13}{'share':>8}   verdict")
    failed = False
    for tier in TIERS:
        used, limit = per_tier[tier], rpd[tier]
        over = used > target * limit
        failed |= over
        note = "ASSUMED limit (original plan)" if tier in assumed else "limit read for this project"
        print(
            f"{tier:<15}{used:>9.0f}{limit:>13}{used / limit:>8.0%}   "
            f"{'OVER the target' if over else 'ok'}; {note}"
        )
    print(f"\n{'feature / tier':<28}{'requests':>9}{'guard limit':>13}   verdict")
    for (feature, tier), used in sorted(totals.items()):
        limit = int(rpd[tier] * shares[tier].get(feature, 0.05))
        print(
            f"{feature + ' / ' + tier:<28}{used:>9.0f}{limit:>13}   "
            f"{'would be REFUSED by its budget' if used > limit else 'fits its budget'}"
        )
    return 1 if failed else 0


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument("--rpd", action="append", default=[], metavar="TIER=N")
    parser.add_argument("--target", type=float, default=0.6)
    parser.add_argument("--rehearsals", type=int, default=Scenario.rehearsals)
    parser.add_argument("--live-runs", type=int, default=Scenario.live_runs)
    parser.add_argument("--visitors", type=int, default=Scenario.visitors)
    parser.add_argument("--coach-reply-tier", choices=TIERS[:3], default="classification")
    parser.add_argument("--no-prewarm", action="store_true", help="team scam checks are new")
    args = parser.parse_args(argv)
    overrides: dict[str, int] = {}
    for item in args.rpd:
        tier, _, number = item.partition("=")
        if tier not in TIERS or not number.isdigit() or int(number) <= 0:
            parser.error(f"--rpd wants TIER=N with a tier from {TIERS}, not {item!r}")
        overrides[tier] = int(number)
    scenario = Scenario(
        rehearsals=args.rehearsals,
        live_runs=args.live_runs,
        visitors=args.visitors,
        prewarmed_team_scam_checks=not args.no_prewarm,
        coach_reply_tier=args.coach_reply_tier,
    )
    rpd, assumed = read_rpd(overrides)
    return report(scenario, rpd, assumed, args.target)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
