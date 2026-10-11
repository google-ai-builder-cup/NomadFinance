from __future__ import annotations

import hashlib
import json

from app.core.cache import TtlCache, log_cache_lookup
from app.integrations.gemini import GeminiClient, ModelTier
from app.prompts.loader import load_prompt
from app.schemas.contract import ReportLanguage
from app.schemas.remittance_compare import ProviderResult, RemittanceComparison
from app.schemas.remittance_recommend import RecommendationAnswer, RemittanceRecommendation
from app.schemas.remittance_trends import RemittanceTrends
from app.utils.i18n import language_name

# Loaded at import so a missing or malformed prompt file stops the app at startup. The
# pipeline records RECOMMEND_PROMPT.key / .version wherever a recommendation is stored.
RECOMMEND_PROMPT = load_prompt("remittance", "recommend", 2)

# What the model said for one comparison in one language. The input holds no worker data (an
# amount, a corridor and the ranked providers), so a repeat from anyone, such as a second visit
# to the same comparison or a demo run twice, costs no request. The rates behind a comparison
# move every two hours, so a short life keeps the text in step with the numbers beside it.
_ANSWERS: TtlCache[RecommendationAnswer] = TtlCache(ttl_seconds=30 * 60, max_entries=256)


def clear_recommendation_cache() -> None:
    _ANSWERS.clear()


class RecommendationIncompleteError(Exception):
    """Gemini's answer is unusable: no text, or a provider other than `recommended_provider`.

    That provider is decided here, from the ranking and the Radar flags, so any other name is
    a wrong answer, not a legitimate override, and is never shown to a worker.
    """


def recommended_provider(comparison: RemittanceComparison) -> ProviderResult:
    """The highest-ranked comparable provider that workers have not flagged, or the
    top-ranked one when every provider is flagged.

    Raises:
        RecommendationIncompleteError: The comparison has no ranked provider.
    """
    ranked = sorted(
        (p for p in comparison.providers if p.comparable and p.rank is not None),
        key=lambda p: p.rank or 0,
    )
    if not ranked:
        raise RecommendationIncompleteError("the comparison has no ranked provider")
    return next((p for p in ranked if not p.flagged), ranked[0])


def _provider_json(provider: ProviderResult) -> dict[str, object]:
    data: dict[str, object] = {
        "rank": provider.rank,
        "firm": provider.firm,
        "fee": provider.fee,
        "fx_margin_pct": provider.fx_margin_pct,
        "total_cost": provider.total_cost,
        "total_cost_pct": provider.total_cost_pct,
        "recipient_receives": provider.recipient_receives,
        "speed": provider.speed,
        "flagged": provider.flagged,
    }
    if provider.flagged:
        data["flag_report_count"] = provider.flag_report_count
    return data


def _comparison_json(comparison: RemittanceComparison, trend: RemittanceTrends | None) -> str:
    """Only what the prompt names: the amount, the ranked comparable providers, and the
    headline numbers. Not sent: `note`, `network_coverage`, the survey block, the exact rate
    and every non-comparable provider — nothing the prompt asks the model to use or mention.
    """
    summary = comparison.summary
    payload: dict[str, object] = {
        "corridor_id": comparison.corridor_id,
        "send_amount": comparison.send_amount,
        "send_currency": comparison.send_currency,
        "receive_currency": comparison.receive_currency,
        "providers": [
            _provider_json(p) for p in comparison.providers if p.comparable and p.rank is not None
        ],
        "best_firm": summary.best_firm,
        "best_recipient_receives": summary.best_recipient_receives,
        "worst_firm": summary.worst_firm,
        "worst_recipient_receives": summary.worst_recipient_receives,
        "extra_vs_worst": summary.extra_vs_worst,
        "mid_market_receives": summary.mid_market_receives,
    }
    if trend is not None and trend.best_day is not None:
        payload["best_day"] = {
            "weekday": trend.best_day.weekday,
            "advantage_pct": trend.best_day.advantage_pct,
        }
    raw = json.dumps(payload, ensure_ascii=False)
    # World Bank firm names are fixed reference data, not worker-supplied text, so this tag
    # could only ever close early by coincidence; neutralised anyway, the same as every other
    # step that sends structured data inside a named block.
    return raw.replace("</comparison", "< /comparison")


def _check_answer(
    answer: RecommendationAnswer, comparison: RemittanceComparison
) -> tuple[int, str]:
    """Return the (rpw_id, firm) the recommendation is actually about, or raise.

    `answer.best_provider` is only ever cross-checked, never trusted: the recommended
    service is always `recommended_provider`.
    """
    if not answer.headline.strip() or not answer.explanation.strip():
        raise RecommendationIncompleteError("the answer has no headline or no explanation")
    expected = recommended_provider(comparison)
    if answer.best_provider.strip().casefold() != expected.firm.strip().casefold():
        raise RecommendationIncompleteError(
            f"the answer recommends {answer.best_provider!r}, not {expected.firm!r}"
        )
    return expected.rpw_id, expected.firm


def _timing_tip(answer: RecommendationAnswer, trend: RemittanceTrends | None) -> str | None:
    if trend is None or trend.best_day is None:
        return None
    return (answer.timing_tip or "").strip() or None


async def generate_recommendation(
    comparison: RemittanceComparison,
    trend: RemittanceTrends | None,
    target_language: ReportLanguage,
    gemini: GeminiClient,
) -> RemittanceRecommendation:
    """Write a short, personal recommendation for a finished comparison. Step 9.

    Args:
        comparison: The unmodified result of `compare_remittance` (steps 1 to 6).
        trend: The result of `get_trends` for the same corridor (step 7), or None.
        target_language: One of the six app languages.
        gemini: Client for the classification tier call.

    Returns:
        `best_provider`, `headline` and `explanation` are written by Gemini in
        `target_language`; `recommended_rpw_id` and `recommended_firm` are
        `recommended_provider` (the best-ranked one workers have not flagged), never
        Gemini's. `timing_tip` is null unless `trend` had a
        `best_day` to report.

    Raises:
        RecommendationIncompleteError: The answer has no text, or names a provider other
            than `recommended_provider`.
        GeminiError: Any Gemini failure, left for the API error handlers.
    """
    comparison_json = _comparison_json(comparison, trend)
    key = hashlib.sha256(f"{target_language}|{comparison_json}".encode()).hexdigest()
    cached = _ANSWERS.get(key)
    log_cache_lookup("remittance", "recommend", hit=cached is not None)
    answer = cached or await gemini.generate_structured(
        operation=RECOMMEND_PROMPT.key,
        tier=ModelTier.CLASSIFICATION,
        contents=RECOMMEND_PROMPT.render_user(
            target_language=language_name(target_language),
            comparison_json=comparison_json,
        ),
        response_model=RecommendationAnswer,
        system_instruction=RECOMMEND_PROMPT.system,
    )
    # The checks run on a cached answer too, against the comparison in hand; only an answer
    # that passed them is kept, so a bad one is asked for again next time.
    rpw_id, firm = _check_answer(answer, comparison)
    _ANSWERS.put(key, answer)
    return RemittanceRecommendation(
        corridor_id=comparison.corridor_id,
        target_language=target_language,
        recommended_rpw_id=rpw_id,
        recommended_firm=firm,
        headline=answer.headline.strip(),
        explanation=answer.explanation.strip(),
        timing_tip=_timing_tip(answer, trend),
    )
