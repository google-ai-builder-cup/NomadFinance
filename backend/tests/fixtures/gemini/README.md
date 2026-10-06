# Recorded Gemini answers

Replayed by `tests/fixtures/fake_gemini.py` (`FakeGemini`), one file per `operation` name. The
format is in that module's docstring. Every recording is synthetic: no real worker's text, no
real contract, no real message.

| File | Operation | Kind |
|---|---|---|
| `contract.detect.json` | `contract.detect` | structured: a detected employment contract |
| `coach.reply.json` | `coach.reply` | text: one coach reply, used by both `chat` and `stream` |
