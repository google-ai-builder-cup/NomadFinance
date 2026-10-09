"""What the Coach guard decides, and the reason codes it logs (NF-FC-013)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

# `allow`: the turn goes on to slot extraction and the reply. `redirect`: a fixed polite line
# brings the worker back to the interview. `refer`: a fixed referral text, no interview question.
GuardAction = Literal["allow", "redirect", "refer"]

# Why, as logged. `_cue` came from the rules, `_model` from the Flash-Lite check; `answer_shaped`
# is the rules' way of letting an ordinary answer through without any model call.
GuardReason = Literal[
    "not_checked",
    "answer_shaped",
    "on_topic_model",
    "model_unsure",
    "injection_cue",
    "injection_model",
    "distress_cue",
    "distress_model",
    "product_request_cue",
    "product_request_model",
    "off_topic_model",
    "reply_recommends_product",
]


@dataclass(frozen=True)
class GuardDecision:
    action: GuardAction
    reason: GuardReason

    @property
    def blocked(self) -> bool:
        return self.action != "allow"

    @property
    def source(self) -> Literal["rule", "model", "none"]:
        if self.reason == "not_checked":
            return "none"
        if self.reason.endswith("_model") or self.reason == "model_unsure":
            return "model"
        return "rule"
