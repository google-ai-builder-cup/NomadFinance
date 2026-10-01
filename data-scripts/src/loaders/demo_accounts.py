"""Create the three demo Firebase Auth accounts (NF-P3-021).

Run from data-scripts/:  python -m src.loaders.demo_accounts
Each demo worker gets an Auth user with the uid used in data/seed/users/*.json and one of the
project's Firebase *test* phone numbers (docs/runbooks/NF-P1-009-frontend-firebase-auth.md).
Signing in with that number then lands on the uid whose history `src.loaders.seed` wrote, so no
`--uid` copy-and-paste is needed. Only the numbers listed here are ever used: they are the
fictional range the console treats as test numbers, so no SMS is sent and no real person is
involved. The accounts hold no password and no Firestore data; the seed loader writes that.

Running again is safe: an account that already matches is left alone, a differing name or number
is updated, and a number that belongs to a different uid is reported, never taken over.
"""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

from firebase_admin import auth  # type: ignore[import-untyped]
from firebase_admin.exceptions import FirebaseError  # type: ignore[import-untyped]
from google.auth.exceptions import DefaultCredentialsError
from pydantic import ValidationError

from src.config import SEED_USERS_DIR
from src.firestore_client import get_firebase_app
from src.validators.demo_user import is_blank, load

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class DemoAccount:
    """A seed file's stem with the display name and test phone number of its Auth user."""

    seed_name: str
    display_name: str
    phone_number: str


# One of the three test numbers each, in the order the runbook lists them.
ACCOUNTS: tuple[DemoAccount, ...] = (
    DemoAccount("priya_sg_domestic", "Priya (demo)", "+61491570156"),
    DemoAccount("rajesh_kr_manufacturing", "Rajesh (demo)", "+61491570157"),
    DemoAccount("miguel_jp_care", "Miguel (demo)", "+61491570158"),
)


class AccountConflictError(Exception):
    """The test number already belongs to another uid; nothing was changed."""


def ensure_account(uid: str, account: DemoAccount) -> str:
    """Make `uid` an Auth user with the account's number and name; returns what was done.

    Raises:
        AccountConflictError: The number is already the sign-in of a different uid.
    """
    try:
        existing = auth.get_user(uid, app=get_firebase_app())
    except auth.UserNotFoundError:
        existing = None
    if existing is None:
        try:
            owner = auth.get_user_by_phone_number(account.phone_number, app=get_firebase_app())
        except auth.UserNotFoundError:
            owner = None
        if owner is not None:
            raise AccountConflictError(
                f"{account.phone_number} already signs in as uid {owner.uid}. Load the history "
                f"under it with `python -m src.loaders.seed --only {account.seed_name} --uid "
                f"{owner.uid}`, or delete that user in the console and run this again."
            )
        auth.create_user(
            uid=uid,
            phone_number=account.phone_number,
            display_name=account.display_name,
            app=get_firebase_app(),
        )
        return "created"
    if existing.phone_number == account.phone_number and (
        existing.display_name == account.display_name
    ):
        return "unchanged"
    auth.update_user(
        uid,
        phone_number=account.phone_number,
        display_name=account.display_name,
        app=get_firebase_app(),
    )
    return "updated"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create the demo Firebase Auth accounts.")
    parser.add_argument("--input-dir", type=Path, default=SEED_USERS_DIR)
    parser.add_argument("--only", nargs="+", metavar="NAME", help="seed file names without .json")
    parser.add_argument(
        "--dry-run", action="store_true", help="Validate and log without touching Firebase Auth"
    )
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")

    wanted = [a for a in ACCOUNTS if not args.only or a.seed_name in args.only]
    unknown = set(args.only or []) - {a.seed_name for a in ACCOUNTS}
    if unknown:
        log.error("no such demo account: %s", ", ".join(sorted(unknown)))
        return 1

    # The uid comes from the seed file, so the account and its data cannot drift apart.
    plan: list[tuple[str, DemoAccount]] = []
    for account in wanted:
        path = args.input_dir / f"{account.seed_name}.json"
        try:
            if is_blank(path):
                log.error("%s is empty: fill it before creating its account", path.name)
                return 1
            plan.append((load(path).uid, account))
        except ValidationError as exc:
            log.error(
                "%s: %d problem(s); run src.validators.demo_user", path.name, exc.error_count()
            )
            return 1
        except (ValueError, OSError) as exc:
            log.error("%s: %s", path.name, exc)
            return 1

    failed = False
    for uid, account in plan:
        if args.dry_run:
            log.info(
                "[dry-run] %s -> uid %s, phone %s", account.display_name, uid, account.phone_number
            )
            continue
        try:
            outcome = ensure_account(uid, account)
        except AccountConflictError as exc:
            failed = True
            log.error("%s: %s", account.display_name, exc)
            continue
        except DefaultCredentialsError:
            log.error("No Google credentials: run `gcloud auth application-default login` first")
            return 1
        except FirebaseError as exc:
            failed = True
            log.error("%s: Firebase Auth refused the request: %s", account.display_name, exc)
            continue
        log.info(
            "%s -> uid %s, phone %s: %s", account.display_name, uid, account.phone_number, outcome
        )
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
