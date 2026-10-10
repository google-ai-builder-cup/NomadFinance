# NF-HR-001 — Coach and scam-check signals in Financial Identity, and the activity feed

## Summary

A worker can now let their **Coach plan check-ins** and their **scam checks** appear in their Financial Identity report. It is opt-in per signal, it is numbers and dates only, and turning it off removes it, in the stored profile at the next weekly recompute and **from every report from the moment they turn it off**. The same activity is listed in one **unified activity feed**.

| Part | What it does |
|---|---|
| **Opt-in** | `users/{uid}.signal_sharing = { coach, scam }` (already allowed by the rules, NF-F0-004). Only a boolean `true` counts. Absent means off |
| **`coach_signal`** | Written at the weekly recompute when `signal_sharing.coach` is true, the `coach` flag is on for the worker and at least one check-in is answered: `{ plan_id, checkins_answered, remittance_on_track, savings_on_track, pay_on_time, last_checkin_at, savings_rate_target_pct, savings_rate_recorded_pct }`. The last two set the plan's own target beside the rate recorded, with no verdict |
| **`scam_signal`** | Same rule with `signal_sharing.scam` and the `scam` flag: `{ window_days: 90, checks, scams_found, last_check_at }`. Never text, indicators or types |
| **Narrative** | Prompt `fib/synthesize_narrative.v2` returns `text` (the four metric paragraphs, as before) and `activity_text` (a short paragraph about what is shared, empty when nothing is). The paragraph is kept only if every number in it is one of the worker's; otherwise the structured rows of the PDF still carry the figures |
| **PDF** | One more section, "Activity the worker chose to share": the counts and dates with fixed wording in six languages, the paragraph, and a note that no message or answer text is included |
| **Opt-out** | The recompute replaces the profile, so signals are gone at the next run. **The export also reads the choice at the moment of the export**, so a worker who stopped sharing on Tuesday gets a report without them on Wednesday. A PDF made while an activity was shared (`latest_export.signals`) is no longer linked once they stop; they export again |
| **Feed** | `GET /api/v1/fib/activity?days=&limit=`: the money log, Coach plans and check-in answers, and scam checks in one list, newest first. The worker's own view: it does not depend on `signal_sharing`, which is about reports others read |

## Files

| File | Change |
|---|---|
| `backend/app/services/fib/signals.py` (new) | `sharing_of`, `coach_signal`, `scam_signal`, `recorded_savings_rate_pct`, `shared_now`, `signals_shown`, `SignalReader` (opt-in, flag, failure isolation). Under `mypy --strict` |
| `backend/app/services/fib/profile_builder.py`, `narrative.py`, `app/schemas/fib_profile.py`, `app/prompts/fib/synthesize_narrative.v2.yaml` (v1 removed) | Signals read and written; the narrative returns two fields; the paragraph's numbers are checked and a drop is logged by its numbers only |
| `backend/app/services/fib/exporter.py`, `report_html.py`, `report_labels.py`, `app/api/v1/fib.py` | The choice read at export; the section and its 12 labels in 6 languages; the latest link withdrawn for a PDF with activity no longer shared |
| `backend/app/services/fib/activity_feed.py`, `app/schemas/fib_activity.py` (new), `app/api/v1/fib.py` | The feed and its route |
| `backend/app/repositories/scam_check_repo.py`, `coach_session_repo.py`, `app/api/v1/internal.py` | `activity_since` (field-masked, one range, no index), `activity` (plans without their bodies); the recompute gets a `SignalReader` |
| `docs/api/endpoints.md`, `docs/data-model/collections/fib.md`, `users.md`, `docs/deferred-items.md` | The contract, the final keys, D-264 to D-267 |

No shared file was touched and no index was added.

## Choices that were not in the task text

| # | Point | What was done |
|---|---|---|
| 1 | The feed and the opt-in | The feed is not behind the opt-in (the worker's own data, as in the Coach and Scam history screens); the opt-in gates only the report |
| 2 | Instant opt-out | The paragraph is a separate field and the export applies the worker's choice itself, so no wait for the weekly job |
| 3 | When a signal exists | Only with data: an answered check-in, or a check in the last 90 days |
| 4 | How "adherence" is measured | The three fixed check-in answers, plus the plan's savings target beside the recorded rate |
| 5 | Scam checks read | One field-masked query (dates and the verdict's flag, level and type), capped at 1,000 |
| 6 | Flags | A signal needs its module on for the worker, like every cross-feature row |
| 7 | Prompt version | v2 replaces v1 on disk, as the other prompts do; profiles record `2` |

## Results

**Backend (2026-10-10):** 3,700 tests pass (175 skipped, the live ones); `black`, `ruff`, `mypy app` and `mypy --strict app/services` clean. About 90 tests are new.

| Check | Result |
|---|---|
| Consent | Only a boolean `true` is consent: `"true"`, `1`, a string, `null`, `{}` and a missing map are all "not shared" |
| The coach signal | Counts the answers of the three milestones; none until one is answered; ignores other milestones and malformed entries; carries no text; the target is the plan's own 9.5% (400 of 4,200) beside the recorded rate, and is left out when either is missing |
| The scam signal | Counts the checks of the 90 days and the flagged ones; one day past the window is out; carries no type or text |
| The reader | Nothing is read without the opt-in or with the module off; a failed read loses that signal only; the window and the cap are what the repository is asked |
| Recompute | Both signals in the profile and the narrative prompt (dates as days); none without opt-in, and the prompt has no `shared_activity`; turning it off removes them at the next run; one shared signal without the other; a failed read does not stop the profile; through the real endpoint |
| The paragraph | "3 October 2026" matches the date `2026-10-03`; "2 of 3" is grounded; a number the worker did not share drops it and is logged by number only; ignored when nothing is shared |
| The PDF | The section appears only with a signal, in the report's language, escaped; `10.0` prints as `10`; one signal off drops the paragraph and that signal's rows |
| The export | Prints what is shared now whatever the stored profile holds, never edits the stored profile; records `signals`; withdraws the link after opt-out; a PDF made with no signals is always linkable |
| The feed | Money log, plans, check-ins and scam checks newest first; no note, name, vendor or message anywhere in the answer; flags gate the Coach and scam events; `days` and `limit` bound it and `truncated` says so; one malformed entry or one failed read leaves the rest |
| Break the rules on purpose | 6 breaks (consent as truthy, the reader ignoring the opt-in, the export printing the stored signals, no check on the paragraph's numbers, the feed ignoring flags, the link ignoring opt-out): each failed a test |

**With the real model (2026-10-10, `gemini-3.5-flash`):** the Hindi report gave a Hindi paragraph, correct and grounded ("2 check-ins ... 7 messages checked, 3 flagged"). A separate English sample with similar figures was grounded too. **In the full run the English paragraph was missing** (empty, or dropped by the numbers check; the quota then ended). The prompt now tells the model a plan has 3 check-ins and a drop is logged. **Not verified live after that change: D-267.**

**Not verified:** the profile-page switches and any screen for the feed (not built: D-265); a real recompute in the emulator with the whole stack; the wording in hi, tl, id, ne and bn by native speakers (D-264).

## Manual test

```bash
cd backend
pytest tests/unit/services/test_fib_signals.py tests/unit/services/test_fib_activity_feed.py \
  tests/unit/services/test_fib_profile_builder.py tests/unit/services/test_fib_exporter.py \
  tests/unit/services/test_fib_report_html.py tests/integration/api/test_fib_activity.py \
  tests/integration/api/test_fib_report_export.py tests/integration/api/test_internal_recompute_fib.py
# with a key in .env.local and quota (prints both paragraphs; read them):
RUN_LIVE_GEMINI=1 pytest tests/integration/api/test_fib_signals_live.py -v -s
```

By hand: in a worker's `users/{uid}` set `signal_sharing: { coach: true, scam: true }` (the profile page cannot yet), have an answered check-in on a plan and a scam check, run `POST /api/v1/internal/recompute-fib-profiles` with the scheduler token, and read `financial_profile/current` for `coach_signal`, `scam_signal` and `narrative.activity_text`. `POST /api/v1/fib/report/export` then prints the section; set both to `false` and export again: the section is gone before any recompute. `GET /api/v1/fib/activity` lists the activity.

## Definition of Done (Backend)

- [x] FIB profile recompute includes the new signals for personas that share them
- [x] Opt-out removes them (from the stored profile at the next recompute, and from every report at once)
- [x] Numbers and dates only: nothing a worker typed or a message said is stored, sent to the model or printed
- [x] Flags off: the signals and the feed's events are inert
- [x] Failures in reading a signal never stop a profile; strict types, lint and format clean
- [x] Feed route, contract and tests; no shared file touched
- [ ] Live English paragraph checked after the change (D-267)
- [ ] Wording read by native speakers (D-264)
- [ ] The profile-page switches and a screen for the feed (D-265, no tracker task)
- [ ] Reviewed by a teammate (Aditya)

## Commit

Branch: `feature/NF-HR-001-integration-fib-signals` (already checked out).

```bash
git commit -m "feat(fib): add shared coach and scam signals and an activity feed" -m "Refs: NF-HR-001"
```

PR title: `feat(fib): coach and scam signals in Financial Identity, and the activity feed (NF-HR-001)`
