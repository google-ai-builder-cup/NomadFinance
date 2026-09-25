# ADR-006: FX Provider Failover Chain

- **Status:** Accepted
- **Date:** 2026-09-25
- **Task:** NF-P1-019

## Context

Remittance X-Ray needs a live mid-market rate for six pairs (`SGD_PHP`, `SGD_INR`, `AUD_INR`, `MYR_IDR`, `JPY_PHP`, `AUD_PHP`). A cron stores them in `rates_cache` and `rates_history` (see `docs/data-model/collections/rates_cache.md`). Free FX APIs go down, change terms, or rate-limit, and one provider failing must not leave the comparison without a rate.

The design doc (section 4.5 and the Remittance cron diagram) names Frankfurter with ExchangeRate-API as fallback. The root README lists four providers. The team chose all four on 2026-09-25.

## Decision

Try the providers in this order and use the first one that returns every requested rate:

| # | Provider | Key | Coverage of our 7 currencies | Updates | Notes |
|---|---|---|---|---|---|
| 1 | Frankfurter (`api.frankfurter.dev/v1/latest`) | none | all (ECB reference rates) | once per working day | primary |
| 2 | ExchangeRate-API open access (`open.er-api.com/v6/latest/{base}`) | none | all | daily | **terms require an attribution link wherever the rates are shown to users** |
| 3 | CurrencyFreaks (`api.currencyfreaks.com/v2.0/rates/latest`) | `CURRENCYFREAKS_API_KEY` | all | per plan | free plan quotes only from USD, so `base→quote = usd_quote / usd_base`; rates arrive as strings |
| 4 | Wise (`api.wise.com/v1/rates`) | `WISE_API_TOKEN` (personal token) | all | live | one request per pair |

Checked on 2026-09-25: Frankfurter and ExchangeRate-API both returned all six pairs; with Frankfurter forced to fail, the chain switched to ExchangeRate-API.

Rules:
- One call per **base currency** (SGD, AUD, MYR, JPY), all quotes at once. A provider that misses any quote counts as failed for that base, so one refresh never mixes providers within a base.
- Timeout 10 s per call (`FX_TIMEOUT_SECONDS`). Bases are fetched in parallel. No retries inside a provider: the next provider is the retry.
- A provider without its key is skipped (`not_configured`). The two keyless providers cover production on their own.
- Every refresh stores the attempt trail in `rates_cache/{pair}.attempts` with short error codes only (`timeout`, `network`, `http_<status>`, `invalid_response`, `missing_quote`, `not_configured`), never response bodies, which can echo keys.
- If every provider fails for a base, those pairs keep their previous `rates_cache` value and the endpoint answers 503, so Cloud Scheduler records a failed run and retries.

Code: `backend/app/integrations/fx/` (`router.py` holds the order).

## Consequences

- Rates are **daily** mid-market rates for the first two providers, even though the cron runs every 2 hours. `rate_date` says which day a rate is for; `fetched_at` says when we checked.
- Adding, removing or reordering a provider is a change to `build_fx_router()` plus a test.
- CurrencyFreaks and Wise keys go in Secret Manager as `currencyfreaks-api-key` and `wise-api-token` (location `asia-south1`, like `gemini-api-key`); `deploy_manual.sh` mounts each one only if it exists, and the Cloud Run service account needs `secretAccessor` on it.
- **Status 2026-09-25:** providers 1–3 are live (`currencyfreaks-api-key` created and mounted; checked on its own, its USD cross rates match the other two within 0.1%). **Wise is not configured:** opening a personal Wise account asks for detailed personal information, and a personal account may not be used for business purposes under Wise's terms. The chain skips it (`not_configured`). If Wise pricing is needed later (for example in the NF-P2-014 comparison), use Wise's official comparison API for price-comparison sites instead of a personal token.
- The frontend (NF-P2-019 comparison table, NF-P2-020 trend chart) must show "Rates by Exchange Rate API" with a link when `provider` is `exchangerate_api`.
