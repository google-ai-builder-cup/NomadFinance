# Remittance X-Ray pipeline

Turns a corridor and an amount into a ranked comparison of every surveyed way to send money home, with the true cost of each, then adds a trend, a savings figure and a recommendation in the worker's language. Design doc section 5.2 and pillar 1; diagram in `docs/mermaid/remittance-xray-pipeline.mmd`; data model in `docs/data-model/collections/corridors.md` and `rates_cache.md`; prompt in `backend/app/prompts/remittance/recommend.v1.yaml`.

Each step's owner adds its section below when the step is built.

## Steps

| # | Step | Task (owner) | Tier (ADR-002) | Code | Status |
|---|---|---|---|---|---|
| 1 | Verify the caller | NF-P1-005 | none | `dependencies.get_current_user` | Built |
| 2 | Fetch the corridor's providers | NF-P2-014 (Pranjal) | none (Firestore) | `repositories/corridor_repo.py` | Built |
| 3 | Fetch the live rate | NF-P2-014 (Pranjal) | none (Firestore) | `repositories/rate_repo.py` `get_rate` | Built |
| 4 | Fetch historical rates | NF-P2-015 (Devam) | none (Firestore) | `services/remittance/trends.py` | Not started |
| 5 | Calculate the true cost of each provider | NF-P2-014 (Pranjal) | none | `services/remittance/engine.py` | Built |
| 6 | Rank by what the recipient receives | NF-P2-014 (Pranjal) | none | `services/remittance/engine.py` | Built |
| 7 | Detect the trend, best day to send | NF-P2-015 (Devam) | none | `services/remittance/trends.py` | Not started |
| 8 | Historical savings against the worker's choice | NF-P2-022 (Devam) | none | not yet named | Not started |
| 9 | Recommendation, in the worker's language | NF-P2-016 (Pranjal) | classification | `services/remittance/recommender.py`, `remittance/recommend.v1` | Not started |
| 10 | Translate | folded into step 9 | | `recommend.v1` writes in the worker's language directly, saving one call | Not needed |
| - | Log a transfer | NF-P2-017 (Aditya) | none | `services/remittance/logger.py` | Not started |
| - | Refresh the rates (cron) | NF-P1-019 (Devam) | none | `services/remittance/rates.py` | Built |

Steps 1 to 6 are one request, `POST /api/v1/remittance/compare` (`docs/api/endpoints.md`). It makes no Gemini call, so the comparison table loads fast and does not spend the Gemini quota that Contract Shield shares (D-58).

## Flow

```
POST /api/v1/remittance/compare   {corridor_id, amount}
  1 get_current_user                                        401 without a token
  2 corridors/{corridor_id}      → CorridorDoc (all providers in one document)   404 if not loaded
  3 rates_cache/{pair}           → RateDoc, or the survey median if none          rate.stale
  5 for each provider: fee + rate markup at this amount   → total cost, recipient receives
  6 rank the comparable providers; list the others last   → RemittanceComparison
  ─ later steps, each its own call, reading the same stored data ─
  4, 7  GET .../trends    rates_history/{pair}/points     → series, best weekday
  8     GET .../savings   history + the survey's margins  → "you would have saved X"
  9     recommend(comparison, trend?, savings?, language) → best_provider, headline, explanation, timing_tip
  -     POST .../log      users/{uid}/transfers           → feeds Financial Identity
cron (every 1 to 2 hours): refresh_rates → rates_cache + rates_history
```

## Where the prices come from

The fees and rate margins are the World Bank's Remittance Prices Worldwide survey, **2025 Q1**, taken from February to early March 2025. It is a published survey of 221 services in the six corridors, not a live price list. Only the mid-market exchange rate is live. Two consequences the app must state:

- Show the survey period and the attribution text (`survey` in the response) wherever a price is shown. The World Bank terms require the attribution.
- A service's real price today may differ. The comparison is a well-founded picture of who is cheap and who is not, not a quote.

## The cost model (step 5)

The World Bank defines the total cost of a service as its flat fee plus its exchange-rate markup, as a percentage of the amount sent:

```
total_cost_pct = fee / amount * 100 + fx_margin_pct
recipient_receives = amount * live_rate * (1 - total_cost_pct / 100)
```

The survey priced two amounts, about USD 200 and 500 (`quote_200`, `quote_500`, for example SGD 260 and 645). The formula was checked against all 442 published quotes: it reproduces `total_cost_pct` to within 0.005 percentage points every time. (Recomputing from `fx_rate` and `interbank_rate` is what differs by up to 0.8 points, because the survey rounds those rates.)

The worker may send any amount, so:

| Amount | Fee and margin used | `estimated` |
|---|---|---|
| Between the two survey amounts | Linear interpolation. 71 of the 221 services have a fee that differs between the two amounts (tiered fees), 3 a margin that does | false |
| Below the smaller or above the larger | The nearest survey point's fee and margin | true |
| Below a quarter of the smaller, or above ten times the larger | Nothing is calculated: `422` with the limits (about USD 50 to 5,000) | |

A flat fee weighs more on a small amount: a 5 SGD fee is 2 % of 250 and 0.5 % of 1,000. The limits keep the answer inside what the survey can honestly be stretched to.

## Ranking (step 6)

- **By what the recipient receives**, best first. Every provider of a corridor is worked out with the same live rate, so the rate changes the amounts and never the order. A test proves it for all six corridors.
- **Ties** (services priced the same) go to the faster service, then by name, then by `rpw_id`, so two identical requests always give the same order.
- **Not comparable:** 6 of 221 services (SG-PH 1, SG-IN 1, JP-PH 4) pay the receiver in USD, not in the receiving currency. What the recipient receives cannot be set against a peso or rupee amount, so they are listed after the ranked ones with `rank: null` and no received amount. Their cost is still shown.
- **A service can cost less than mid-market.** Five of the published quotes have a negative total cost: InstaReM on AU-IN at both survey amounts, and three MoneyGram services on AU-PH at the larger one. They are shown as they are: `lost_to_costs` is negative and the service ranks first.
- **A firm is not a service.** Wise, for example, appears several times in one corridor (13 firms repeat in SG-PH), once per payment method and access point. The key of a service is `rpw_id`. Anything that refers to a service (a logged transfer, the recommendation's `best_provider`) should carry both `rpw_id` and `firm`. A radar flag (NF-P3-022) is about a firm: match it by name.

## The live rate (step 3)

`rates_cache/{pair}` is written by the cron. The comparison uses its `rate` and reports `fetched_at`. It is `stale` when older than 6 hours (`RATE_MAX_AGE` in `constants.py`): the cron runs every 1 to 2 hours, so that means at least two runs failed. When the pair has no document yet, the median of the survey's own mid-market rates is used, with `source: "survey"` and `stale: true`, so a comparison still works and the app can say the rate is old. Every call is one corridor read and one rate read; there is no cache in the process.

## How the later steps attach

These are the contracts the built step offers. Their owners decide the details.

- **Trends and best day (steps 4 and 7, NF-P2-015).** Reads `rates_history/{pair}/points` for the same pair (`constants.pair_for_corridor`). A separate call from the comparison, so a slow history read never delays the table. The comparison already carries `rate.pair`.
- **Savings (step 8, NF-P2-022).** Uses the history and the survey's margins; the cost model above is the same function (`engine._terms`) and should be reused, not copied.
- **Recommendation (step 9, NF-P2-016).** `recommend.v1` takes the comparison as JSON (`<comparison>`) and returns `best_provider`, `headline`, `explanation`, `timing_tip`, in the worker's language. `RemittanceComparison` already holds everything the prompt names: the amount and corridor, providers ranked by what the recipient receives, fee and markup per provider, `extra_vs_worst` and `mid_market_receives`. Trend and savings are added by their steps. The prompt copies numbers, it never calculates them, so the figures come from this step. Keep it a separate call from `/compare`: it is the only step that needs Gemini.
- **Radar flags (NF-P3-022).** A `flagged` field per firm can be added to `ProviderResult` when `radar_entities/` exists.
- **Transfer log (NF-P2-017).** A logged transfer can carry `corridor_id`, `rpw_id`, `firm`, the amount, `fee`, `total_cost_pct` and `rate.rate` from the comparison the worker chose from.
- **Frontend (NF-P2-018, NF-P2-019).** `speed_order` sorts the speed column; `estimated` and `rate.stale` need a visible note; `survey.attribution` must be on screen.

## Errors

| Status | When |
|---|---|
| 401 | No or invalid token |
| 404 | The corridor is not loaded in Firestore, or none of its services can be compared |
| 422 | Unknown corridor, or an amount that is missing, not a number, not above 0, or outside the limits of the corridor |
| 429 | Over the API-wide budget (60 a minute) |

A damaged corridor document is a server error (500), never a wrong answer. The request log holds the corridor, counts, the rate source and staleness, never the amount.
