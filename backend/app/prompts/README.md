# Prompt library

Every Gemini prompt of NomadFinance, one YAML file per pipeline step and version (NF-P1-029). Code never contains prompt text; it loads a file and fills in the values.

```
app/prompts/<pillar>/<step>.v<N>.yaml
```

| File | Step (task) | Tier (ADR-002) | Variables |
|---|---|---|---|
| `contract/extract.v2` | Transcribe the upload as ordered blocks: clauses, tables, pages (NF-P1-006, NF-P2-001; v1 removed) | extraction | none: the file is a separate part |
| `contract/detect.v2` | Language, host country, document kind, job type, employer/agency/salary incl. daily wages (NF-P2-002; v1 removed) | extraction | `contract_text` |
| `contract/compare.v1` | Clause-by-clause check against the labor-law rules (NF-P2-004) | reasoning | `job_type`, `host_country_name`, `law_rules_json`, `contract_text` |
| `contract/translate.v1` | Report into the worker's language (NF-P2-005, NF-P2-012) | classification | `target_language`, `report_json` |
| `contract/complaint.v2` | Complaint letter from the authority template, for the authority and as a copy in the worker's language (NF-P2-006; v1 removed) | reasoning | `worker_language`, `template_json`, `violations_json`, `contract_facts_json` |
| `remittance/recommend.v2` | Recommendation, written directly in the worker's language; passes over providers flagged on the Exploitation Radar (NF-P2-016; v1 removed) | classification | `target_language`, `comparison_json` |
| `radar/extract_entity.v1` | Who and where a report is about (NF-P3-001) | extraction | `form_json`, `report_text` |
| `radar/validate.v1` | Spam score, abuse, personal data (NF-P3-001) | classification | `entity_json`, `report_text` |
| `radar/categorize.v1` | Violation type and a one-line English summary (NF-P3-001) | classification | `entity_json`, `report_text` |
| `fib/extract_bill.v1` | Read a bill photo (NF-P3-011) | extraction | none: the image is a separate part |
| `fib/categorize.v1` | Categories for a batch of entries (NF-P3-012) | classification | `entries_json` |
| `fib/synthesize_narrative.v1` | Financial Identity report text (NF-P3-013) | reasoning | `report_language`, `profile_json` |
| `scam/classify.v2` | Is a pasted message a scam: type, tactics, risk, trigger phrases, details; v2 also gets the fixed rules' signals, flags and amounts but never a link or number (NF-SA-007, NF-SA-011; v1 removed) | classification | `taxonomy_json`, `signals_json`, `message` |
| `scam/read_screenshot.v1` | Transcribe a message screenshot: text and visible sender (NF-SA-008) | extraction | none: the image is a separate part |
| `scam/explain.v1` | For a scam: why each detected tactic works, what the scammer wants, 3 safe next steps, in the worker's language at grade 6 (NF-SA-009) | reasoning | `language`, `host_country`, `verdict_json`, `details_json`, `tactics_json`, `tactic_notes_json`, `safe_response_json`, `message` |
| `scam/reassure.v1` | For a message that is not a scam: a short reassurance and one general tip (NF-SA-009) | classification | `language`, `details_json`, `message` |
| `coach/translate_plan.v1` | Translate a finished plan's sentences into the worker's language; only text is sent, and every number and currency code must come back unchanged (NF-FC-014) | classification | `target_language`, `plan_json`, `fix_these` |
| `coach/plan.v1` | The words of the 90-day plan: summary, 13 weeks of actions, the warnings and checklist items code chose; it is given the figures and may use no other number, which the validator checks (NF-FC-012) | reasoning | `facts_json`, `warnings_json`, `checklist_json`, `fix_these` |
| `coach/extract.v1` | Read one worker message in any of the six languages into interview answers: for each, the exact words that state it and a confidence; the code checks every one before it is kept (NF-FC-010) | classification | `worker_language`, `today`, `asking`, `unconfirmed_json`, `confirmed_json`, `recent_talk`, `message` |
| `coach/guard.v1` | Sort one worker message as on topic, off topic, a request for a financial product, an order to the coach, or a sign of danger; asked only for messages the fixed rules cannot judge, and it never writes to the worker (NF-FC-013) | classification | `worker_language`, `asking`, `message` |
| `coach/reply.v2` | The coach's next message, streamed, in the worker's language: the next question from the question bank, a follow-up when an answer was unclear, a lead-in to the review (it writes no figure there), or a closing line; it may use only figures it is given (NF-FC-009; v2 in NF-FC-023, v1 removed) | classification | `language`, `stage`, `first_message`, `ask_next`, `follow_up`, `understood_json`, `slots_json`, `summary`, `worker_message` |
| `coach/review.v1` | Read the worker's reply at the review as confirm, change (and which answer) or other; the code checks the quoted words and needs 0.85 confidence for a confirm (NF-FC-020) | classification | `answers_json`, `message` |
| `coach/summarise.v1` | Notes in English of the turns an interview's history window left out, kept exactly as said and sent back to the reply prompt (NF-FC-009) | classification | `earlier_summary`, `turns` |

The fields each prompt asks for are the field names in `docs/data-model/collections/`. The step's Pydantic response model (the `response_schema`) must use the same names.

## File format

```yaml
description: >
  What the step does, which task and endpoint use it, and the tier.

system: |
  Instructions. No placeholders here: it is sent as the system instruction as is.

user: |
  The request, with placeholders for the values of one call.

  <contract_text>
  ${contract_text}
  </contract_text>

variables: [contract_text]
```

- `description`, `system` and `user` are required; `variables` lists every `${name}` in `user` (leave it out when there are none). Unknown keys are rejected.
- The loader checks at startup that the placeholders in `user` and `variables` match exactly, that `system` has none, and that no `$` is malformed. A literal dollar sign in `user` must be written `$$`.
- The tier, temperature and response model are chosen in the calling code, not in the file.

## Using a prompt

```python
from app.prompts.loader import load_prompt
from app.utils.i18n import language_name

# Load at import, so a missing or broken file stops the app at startup.
_PROMPT = load_prompt("contract", "translate", 1)

result = await gemini.generate_structured(
    operation=_PROMPT.key,                      # "contract.translate", for logs and cost
    tier=ModelTier.CLASSIFICATION,
    contents=[_PROMPT.render_user(target_language=language_name("ne"), report_json=report_json)],
    response_model=TranslatedReport,
    system_instruction=_PROMPT.system,
)
prompt_versions = {_PROMPT.key: _PROMPT.version}  # stored on the result (docs/data-model/versioning.md)
```

`render_user()` raises `ValueError` when a declared value is missing or an undeclared one is passed. Values are inserted once, so `${...}` inside a worker's text stays literal.

## Text from workers is data, not instructions

Contracts, reports, bills and notes come from workers, and anyone can type "ignore your instructions" into them. Every prompt therefore:

- puts that text inside a named tag (`<contract_text>`, `<report>`, `<entries>`, ...), and
- says in `system` that everything in those blocks is content and that instructions inside it are never followed.

A test fails if a prompt's `system` lacks that sentence. Pass structured inputs as JSON (`json.dumps(..., ensure_ascii=False)`), never by pasting fields into sentences.

## Changing a prompt

- **Before any stored result uses it** (the step is not built yet): edit the `.v1` file.
- **After results are stored**: a wording change that can change results is a **new file** (`compare.v2.yaml`), and the code loads version 2. Keep `v1` until nothing loads it. Editing a used file in place would make old cached reports look current (`docs/data-model/versioning.md`).
- Add the new file to `EXPECTED_PROMPTS` in `tests/unit/test_prompt_loader.py`.
- Try it on real inputs before merging, including an awkward one: a photo, a non-English text, a text containing instructions.

## Checks

```bash
python -m pytest tests/unit/test_prompt_loader.py -q
```

The tests load every file, check the placeholders and the injection guard, render each template, and check that the library holds exactly the expected prompts.
