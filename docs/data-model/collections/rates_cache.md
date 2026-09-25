# rates_cache and rates_history

Shape sources: the two paths are **[D]** (with `points` needing a document id, see `firestore-schema.md`). The fields are **[P]**, based on the Remittance pipeline diagram (cron every 2 hours, provider failover, historical rates for trends), the four-provider chain in the root README (Frankfurter, ExchangeRate-API, CurrencyFreaks, Wise), and NF-P1-019, NF-P2-015, NF-P2-020, NF-P2-022.

## Currency pairs

The six pairs the six corridors need (the `from` and `to` are the corridor's source and destination currencies):

| Pair id | Corridor |
|---|---|
| `SGD_PHP` | SG-PH |
| `SGD_INR` | SG-IN |
| `AUD_INR` | AU-IN |
| `MYR_IDR` | MY-ID |
| `JPY_PHP` | JP-PH |
| `AUD_PHP` | AU-PH |

## `rates_cache/{pair}`

The latest live mid-market rate for one pair. Overwritten on every refresh, so there are always exactly six documents.

| Field | Type | Required | Description |
|---|---|---|---|
| `base_currency`, `quote_currency` | string | yes | ISO-4217. `rate` is units of the quote currency for 1 unit of the base. |
| `rate` | number | yes | Mid-market rate |
| `provider` | string | yes | Which provider answered: `frankfurter`, `exchangerate_api`, `currencyfreaks`, `wise` |
| `rate_date` | string (date) | yes | The date the provider says the rate is for |
| `fetched_at` | timestamp | yes | When the cron got it. A rate older than the refresh interval plus a margin is stale; readers decide, the document has no `stale` flag that could itself go stale. |
| `attempts` | array of map | no | The failover trail for this refresh, for example `[{ "provider": "frankfurter", "ok": false, "error": "timeout" }, { "provider": "exchangerate_api", "ok": true }]`. Keep only short error codes, never response bodies. |
| `corridor_ids` | array of string | yes | Corridors that use this pair |
| `schema_version` | number | yes | `1` |

**Example** — `rates_cache/SGD_PHP`

```json
{
  "base_currency": "SGD",
  "quote_currency": "PHP",
  "rate": 43.31,
  "provider": "frankfurter",
  "rate_date": "2026-09-27",
  "fetched_at": "2026-09-27T08:00:03Z",
  "attempts": [{ "provider": "frankfurter", "ok": true }],
  "corridor_ids": ["SG-PH"],
  "schema_version": 1
}
```

The rate value is illustrative.

## `rates_history/{pair}` and `rates_history/{pair}/points/{pointId}`

The parent `rates_history/{pair}` is a small header: `{ "base_currency": "SGD", "quote_currency": "PHP", "updated_at": ... }`.

Each point is one observation, used for trend charts, "best day to send" and the "you would have saved" calculation.

**Point id:** the UTC hour, `2026-09-27T08`. It is derived from the time, so running the cron twice in the same hour overwrites the same point instead of adding a duplicate. Backfilled daily points use hour `00`, for example `2026-03-01T00`.

| Field | Type | Required | Description |
|---|---|---|---|
| `at` | timestamp | yes | The observation time (start of the hour) |
| `rate` | number | yes | Same meaning as `rates_cache.rate` |
| `provider` | string | yes | Provider that answered |
| `source` | string | yes | `cron` or `backfill` |

**Example** — `rates_history/SGD_PHP/points/2026-09-27T08`

```json
{
  "at": "2026-09-27T08:00:00Z",
  "rate": 43.31,
  "provider": "frankfurter",
  "source": "cron"
}
```

### Volume

| Item | Count |
|---|---|
| Cron writes per run | 6 in `rates_cache` and 6 in `rates_history` |
| At one run per hour | 288 writes per day (the free tier allows 20,000) |
| New history documents per year | About 52,600 (6 pairs times 24 hours times 365 days) |

If storage ever matters, a TTL policy on a `delete_after` field can prune old hourly points while keeping daily ones. That is not needed for the prototype.

### Notes

- **Cron interval.** The design doc and diagrams say every 2 hours; NF-P1-019 says hourly. The point id works for either. The schedule itself is set in Cloud Scheduler, not here.
- **Backfill.** `data-scripts/src/loaders/frankfurter_backfill.py` (stub) fills daily points so the trend chart has a history on day one. Set `source: "backfill"`.
- **Rate for the recipient-receives calculation.** Use the corridor's RPW `fx_rate` and `interbank_rate` from [corridors](corridors.md) for the provider comparison; `rates_cache` is the current mid-market reference and the base for savings and trend features.

## Access and tasks

- **Access:** signed-in users read; only the cron and backfill write.
- **Index:** none beyond the automatic ones. `points` are read with a range on `at`, which the automatic single-field index handles.
- **Tasks:** NF-P1-019 (cron and endpoint), NF-P2-014 (comparison), NF-P2-015 (trends endpoint), NF-P2-020 (trend chart), NF-P2-022 (savings calculator).
