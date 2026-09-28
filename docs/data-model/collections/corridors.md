# corridors

Shape source: **[built]**. The document body is exactly one entry of `corridors[]` in `data-scripts/data/processed/rpw_corridors.json`, written by the World Bank parser (NF-P1-015) and validated by `data-scripts/src/validators/corridor.py`. The path `corridors/{corridor_id}` is **[D]**. The two fields added by the loader (`source`, `loaded_at`) are **[P]**.

## `corridors/{corridorId}`

Six documents, one per project corridor: `SG-PH`, `SG-IN`, `AU-IN`, `MY-ID`, `JP-PH`, `AU-PH`. The providers are kept **inside** the document as an array, not as a subcollection, because the comparison engine (NF-P2-014) always needs all of them together. One document read returns a whole corridor. The largest document, `JP-PH` with 44 providers, is about 26 KB, far below the 1 MiB limit.

The data is real World Bank Remittance Prices Worldwide data for **2025 Q1**. It is a survey of published prices, not a live feed. Show `surveyed_on` to users.

### Corridor fields

| Field | Type | Required | Description |
|---|---|---|---|
| `corridor_id` | string | yes | Same as the document id |
| `source_country`, `destination_country` | string | yes | ISO-2 |
| `source_currency`, `destination_currency` | string | yes | ISO-4217 |
| `period` | string | yes | RPW survey quarter, for example `2025_1Q` |
| `provider_count` | number | yes | Length of `providers` |
| `providers` | array of map | yes | One entry per surveyed service, never empty |
| `source` | map | yes | Added by the loader: `name`, `url`, `attribution` copied from the JSON. The attribution text is required by the World Bank terms wherever the data is shown. |
| `loaded_at` | timestamp | yes | Added by the loader. Set on each load. |

### Provider fields (each entry of `providers`)

| Field | Type | Description |
|---|---|---|
| `rpw_id` | number | RPW's id for the service. Unique in the document. |
| `firm` | string | Provider name, for example `Wise` |
| `firm_type` | string | `Money Transfer Operator`, `Bank`, `Mobile Operator` or `Post Office` |
| `payment_instrument` | string | How the sender pays: `Cash`, `Bank account transfer`, `Debit card`, `Credit card`, `Mobile money` |
| `access_point` | string | Where the sender starts (`Internet`, `Agent`, `Bank branch`, ...) |
| `pickup_method` | string | How the receiver collects (`Bank account`, `Cash`, `Mobile wallet`, ...) |
| `speed` | string | For example `Same day` |
| `network_coverage` | string or null | `High`, `Medium`, `Low` |
| `note` | string or null | RPW's own note |
| `payout_currency` | string | The currency the receiver gets. **Usually the destination currency, but `USD` for 6 services** (DBS, GoRemit, Japan Post Bank, Metro Bank). For those, `fx_rate` is not comparable with local-currency providers. |
| `interbank_rate` | number | Mid-market rate on the survey date |
| `surveyed_on` | string (date) | Kept as a `YYYY-MM-DD` string |
| `quote_200`, `quote_500` | map | The price of sending USD 200 and USD 500, see below |

Quote map (amounts are in the **sender's** currency):

| Field | Description |
|---|---|
| `send_amount_lcu` | Amount that equals USD 200 or 500 |
| `fee_lcu` | Flat fee |
| `fx_rate` | Rate applied by the provider (payout currency per 1 unit of sending currency) |
| `fx_margin_pct` | How much worse than the interbank rate; negative means better |
| `total_cost_pct` | Fee plus rate margin as a percentage of the amount sent. **Rank by this.** Do not recompute it from `fx_rate` and `interbank_rate`: that differs by up to 0.8 percentage points because RPW rounds its published rates. It is exactly `fee_lcu / send_amount_lcu * 100 + fx_margin_pct` (all 442 quotes agree to 0.005 points), which is how the comparison engine (NF-P2-014) prices amounts other than the two survey amounts. |

`total_cost_pct` can be negative (5 quotes in the 2025 Q1 data), and that is real.

**Example** — `corridors/SG-PH` (first provider only; the real document has 39)

```json
{
  "corridor_id": "SG-PH",
  "source_country": "SG",
  "destination_country": "PH",
  "source_currency": "SGD",
  "destination_currency": "PHP",
  "period": "2025_1Q",
  "provider_count": 39,
  "providers": [
    {
      "rpw_id": 521252425,
      "firm": "A-Express Remit",
      "firm_type": "Money Transfer Operator",
      "payment_instrument": "Cash",
      "access_point": "Agent",
      "pickup_method": "Bank account",
      "speed": "Same day",
      "network_coverage": "Medium",
      "note": null,
      "payout_currency": "PHP",
      "interbank_rate": 43.219675797,
      "surveyed_on": "2025-02-20",
      "quote_200": { "send_amount_lcu": 260.0, "fee_lcu": 5.0, "fx_rate": 42.95, "fx_margin_pct": 0.62, "total_cost_pct": 2.54 },
      "quote_500": { "send_amount_lcu": 645.0, "fee_lcu": 5.0, "fx_rate": 42.95, "fx_margin_pct": 0.62, "total_cost_pct": 1.4 }
    }
  ],
  "source": {
    "name": "World Bank Remittance Prices Worldwide",
    "url": "http://remittanceprices.worldbank.org",
    "attribution": "The World Bank, Remittance Prices Worldwide, available at http://remittanceprices.worldbank.org"
  },
  "loaded_at": "2026-09-27T08:00:00Z"
}
```

The example is a shortened copy of the real document, so `provider_count` does not match the array length here. The real document does.

## Loading and refreshing (NF-P1-016)

- Loader: `data-scripts/src/loaders/corridors.py` (`python -m src.loaders.corridors`), backed by `data-scripts/src/firestore_client.py` (Firebase Admin SDK, Application Default Credentials).
- Write each corridor with a plain `set` on `corridors/{corridor_id}`. The id is fixed, so running the loader again replaces the document and never duplicates it.
- Check each document against the Pydantic models in `data-scripts/src/validators/corridor.py` before writing.
- When the World Bank publishes a newer quarter, re-run the parser, then the loader. `period` changes and old data is replaced. There is no history of past quarters in Firestore.

## Access and tasks

- **Access:** signed-in users read; only the data script writes.
- **Index:** none beyond the automatic single-field ones.
- **Tasks:** NF-P1-015 (parser), NF-P1-016 (loader), NF-P2-014 (comparison engine), NF-P2-018 and NF-P2-019 (UI), NF-P3-022 (radar badge on a provider).
