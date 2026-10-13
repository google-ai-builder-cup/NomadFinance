"""Turn `quota-limits.json` and `alert-policy.template.json` into one alert policy per model.

Run by `setup-monitoring.sh`:

    python3 render_policies.py OUT_DIR [NOTIFICATION_CHANNEL ...]

Also writes `OUT_DIR/service-<name>.json` for each file of `service-alerts/` (the server-error and
slow-request alerts of NF-HR-017), which need no limit.

Writes `OUT_DIR/<model>.json` for each model whose `rpd` (requests per day) is filled in, with the
alert threshold at `alert_at_fraction` of it. A model whose `rpd` is still null is skipped and named
on stderr: its alert cannot be made until someone reads the real limit in Google AI Studio.
Exit code 3 means at least one model was skipped, so a script that goes on cannot hide it.
"""

from __future__ import annotations

import json
import math
import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent
SKIPPED_EXIT_CODE = 3


def render_policies(
    limits: dict[str, Any], template: dict[str, Any], channels: list[str]
) -> tuple[dict[str, dict[str, Any]], list[str]]:
    """Returns the policies by model, and the models skipped for want of a limit."""
    fraction = float(limits["alert_at_fraction"])
    if not 0 < fraction <= 1:
        raise ValueError(
            f"alert_at_fraction must be above 0 and at most 1, not {fraction}"
        )
    text = json.dumps(template)
    rendered: dict[str, dict[str, Any]] = {}
    skipped: list[str] = []
    for model, entry in limits["models"].items():
        rpd = entry["rpd"]
        if rpd is None:
            skipped.append(model)
            continue
        if not isinstance(rpd, int) or isinstance(rpd, bool) or rpd <= 0:
            raise ValueError(
                f"rpd for {model} must be a whole number above 0, not {rpd!r}"
            )
        threshold = math.floor(rpd * fraction)
        policy: dict[str, Any] = json.loads(
            text.replace("__MODEL__", model)
            .replace("__THRESHOLD__", str(threshold))
            .replace("__RPD__", str(rpd))
        )
        policy["conditions"][0]["conditionThreshold"]["thresholdValue"] = threshold
        if channels:
            policy["notificationChannels"] = channels
        rendered[model] = policy
    return rendered, skipped


def render_service_alerts(
    directory: Path, channels: list[str]
) -> dict[str, dict[str, Any]]:
    """The fixed policies of `service-alerts/` (server errors, slow requests), by file name.

    They need no limit, so they are made even when a model has none. Only the notification
    channels are added.
    """
    rendered: dict[str, dict[str, Any]] = {}
    for file in sorted(directory.glob("*.json")):
        policy: dict[str, Any] = json.loads(file.read_text(encoding="utf-8"))
        if channels:
            policy["notificationChannels"] = channels
        rendered[f"service-{file.stem}"] = policy
    return rendered


def main(argv: list[str]) -> int:
    if len(argv) < 2:
        print(__doc__, file=sys.stderr)
        return 2
    out_dir = Path(argv[1])
    limits = json.loads((HERE / "quota-limits.json").read_text(encoding="utf-8"))
    template = json.loads(
        (HERE / "alert-policy.template.json").read_text(encoding="utf-8")
    )
    policies, skipped = render_policies(limits, template, argv[2:])
    out_dir.mkdir(parents=True, exist_ok=True)
    for model, policy in policies.items():
        (out_dir / f"{model}.json").write_text(
            json.dumps(policy, indent=2), encoding="utf-8"
        )
        print(f"rendered {model}")
    for name, policy in render_service_alerts(
        HERE / "service-alerts", argv[2:]
    ).items():
        (out_dir / f"{name}.json").write_text(
            json.dumps(policy, indent=2), encoding="utf-8"
        )
        print(f"rendered {name}")
    for model in skipped:
        print(f"SKIPPED {model}: no rpd in quota-limits.json", file=sys.stderr)
    return SKIPPED_EXIT_CODE if skipped else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
