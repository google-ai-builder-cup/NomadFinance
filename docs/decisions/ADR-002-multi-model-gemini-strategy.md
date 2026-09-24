# ADR-002: Multi-Model Gemini Strategy

- **Status:** Accepted
- **Date:** 2026-09-24
- **Task:** NF-P1-004

## Context

Every pillar calls Gemini, but the calls differ a lot in how hard they are and how often they run: a few legal-reasoning calls per contract, one vision extraction per document, and many cheap classification, validation and translation calls. Using one model for everything either overpays for the cheap calls or underpowers the reasoning.

The design doc planned Gemini 2.5 Flash (reasoning), 1.5 Flash (extraction) and 2.0 Flash-Lite (classification). On 2026-09-24 Google's model list showed:

| Planned model | Status on 2026-09-24 |
|---|---|
| `gemini-2.5-flash` | Limited Access: only for users who actively used 2.5 models in the past. The team's key (created 2026-09-21) does not qualify. |
| `gemini-1.5-flash` | Not listed (retired) |
| `gemini-2.0-flash-lite` | Shut down |
| `text-embedding-004` | Not listed; the stable embedding model is `gemini-embedding-001` |

## Decision

Keep three tiers, one model per tier, all configurable through env vars:

| Tier (`ModelTier`) | Used for | Default model | Env override |
|---|---|---|---|
| `REASONING` | Contract legal analysis, complaint letters, financial narratives | `gemini-3.5-flash` | `GEMINI_MODEL_REASONING` |
| `EXTRACTION` | Vision and document extraction (contracts, bills, receipts) | `gemini-3.5-flash-lite` | `GEMINI_MODEL_EXTRACTION` |
| `CLASSIFICATION` | Radar validation, categorisation, translation, recommendations | `gemini-3.1-flash-lite` | `GEMINI_MODEL_CLASSIFICATION` |

Why these models:

1. **They answer on the free tier today.** Live structured calls on 2026-09-24 with the team key (`scripts/gemini_smoke_test.py`):

   | Model | Result |
   |---|---|
   | `gemini-3.8-flash`, `gemini-3.7-flash`, `gemini-3.6-flash` | `503 UNAVAILABLE` "experiencing high demand" on every attempt, across several runs |
   | `gemini-3.5-flash` | OK. Correct legal verdict (passport retention is illegal in Singapore); occasional 503 that the retry recovers from. |
   | `gemini-3.5-flash-lite` | OK. Extracted employer, salary and currency from a PDF correctly, with no thinking tokens (569 tokens versus 860 on 3.5 Flash). |
   | `gemini-3.1-flash-lite` | OK. Language detection. |

2. **All are on the free tier** ("Free of charge" input and output on the pricing page).
3. **Separate quotas.** Free-tier rate limits are per model, so three different models give three separate daily quotas instead of one shared one. The exact RPM/RPD per project is only shown in AI Studio (Rate limits page), not in the public docs.
4. **Cost if we move to paid** (per 1M tokens, input/output): 3.5 Flash $1.50/$9.00, 3.5 Flash-Lite $0.30/$2.50, 3.1 Flash-Lite $0.25/$1.50. Only the reasoning tier uses the expensive model, and it has the lowest call volume.
5. **Capabilities.** All three take text, image and PDF input and support structured output. Only the reasoning tier spends thinking tokens.

**Revisit:** `gemini-3.8-flash` was the first choice for reasoning (stronger, and cheaper on paid at $0.75/$3.75, a promotional price listed through 2026-12-31) but was unavailable on the free tier during testing. When it answers the smoke test reliably, or once billing is enabled, switch with `GEMINI_MODEL_REASONING=gemini-3.8-flash`. No code change is needed.

All code picks a model through `ModelTier` (`app/integrations/gemini/model_tiers.py`), never by hard-coding a model ID, so a model swap is an env var change.

## Consequences

- Retirements like the ones above cost one env var change and a redeploy, not a code change.
- The design doc and the Definition of Done in the task tracker still name 2.5 / 1.5 / 2.0 models. Read their tier names as `REASONING` / `EXTRACTION` / `CLASSIFICATION`, and this ADR as the source for the model IDs.
- Embeddings (NF-P3-002) should use `gemini-embedding-001`, not `text-embedding-004`.
- **Data use on the free tier.** Google's pricing page says free-tier content is "used to improve our products". Contracts and bills contain workers' personal data. Free tier is acceptable for the prototype with demo data. Real user data needs a billing-enabled (paid tier) key.
