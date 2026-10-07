"""Shared pieces of the Scam Analyzer's explainer tests (NF-SA-009).

The model's answer is rebuilt from each analyze mock's `explainer` (`docs/mocks/scam/`), so the
endpoint is checked against the very JSON the frontend builds on: if the service changed what
it returns, the mock and the test would disagree.
"""

from __future__ import annotations

from typing import Any

from tests.fixtures.scam_classify import classify_recording, load_mock_body, model_answer


def explain_answer(body: dict[str, Any]) -> dict[str, Any]:
    """What the explainer model would have returned for the mock's message."""
    explainer = body["explainer"]
    if explainer["kind"] == "scam":
        return {
            "why_it_works": explainer["why_it_works"],
            "scammer_wants": explainer["scammer_wants"],
            "next_steps": explainer["next_steps"],
        }
    return {"reassurance": explainer["reassurance"], "tip": explainer["tip"]}


def explain_operation(body: dict[str, Any]) -> str:
    return "scam.explain" if body["explainer"]["kind"] == "scam" else "scam.reassure"


def recordings_for(case: str) -> dict[str, Any]:
    """Classify and explain recordings for one mock case (`high`, `medium`, `low`, `benign`)."""
    body = load_mock_body(case)
    return {
        "scam.classify": classify_recording(model_answer(body)),
        explain_operation(body): {"kind": "structured", "response": explain_answer(body)},
    }
