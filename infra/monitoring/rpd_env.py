"""Print `quota-limits.json` as the `GEMINI_RPD_*` settings the backend's budget guard reads.

Run by `backend/scripts/deploy_manual.sh`, which appends the output to `--set-env-vars`:

    python3 rpd_env.py        ->   ,GEMINI_RPD_REASONING=500,GEMINI_RPD_CLASSIFICATION=1500

The alerts (`render_policies.py`) and the guard thus read one file, and cannot disagree about a
model's daily limit. A model whose `rpd` is still null adds nothing, which leaves the guard off
for that tier (it is named on stderr). `--set-env-vars` replaces every variable on the service,
so the limits have to travel with each deploy instead of being set by hand.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent


def rpd_env(limits: dict[str, Any]) -> tuple[list[str], list[str]]:
    """The `NAME=value` pairs for the models with a limit, and the models without one."""
    pairs: list[str] = []
    unset: list[str] = []
    for model, entry in limits["models"].items():
        rpd = entry["rpd"]
        if rpd is None:
            unset.append(model)
            continue
        if not isinstance(rpd, int) or isinstance(rpd, bool) or rpd <= 0:
            raise ValueError(f"rpd for {model} must be a whole number above 0, not {rpd!r}")
        pairs.append(f"GEMINI_RPD_{entry['tier']}={rpd}")
    return pairs, unset


def main() -> int:
    limits = json.loads((HERE / "quota-limits.json").read_text(encoding="utf-8"))
    pairs, unset = rpd_env(limits)
    for model in unset:
        print(f"no rpd for {model} in quota-limits.json: its budget guard stays off", file=sys.stderr)
    sys.stdout.write("".join(f",{pair}" for pair in pairs))
    return 0


if __name__ == "__main__":
    sys.exit(main())
