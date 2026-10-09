// The Financial Coach contract through the mock API (NF-FC-002): every route of
// docs/api/v2-coach.md answers from docs/mocks/coach/, and a streamed turn is replayed from an
// .sse file, so the chat and score screens (NF-FC-017, -020, -021) can be built and tested
// before the backend exists. The backend checks the same files against its own models
// (backend/tests/unit/test_coach_mocks.py), so the two cannot drift apart.
//
// The reader below is the smallest one that proves the files replay. The app's own reader
// (fetch plus a stream reader, with retry) is NF-FC-017's job.
import { describe, expect, it } from "vitest";

import { handlerForMock, sseHandler } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";

setupMockServer();

const API = "http://localhost/api/v2/coach";
const PLAN_ID = "5a202702c922fc9b4fcf";

interface SseEvent {
  event: string;
  data: Record<string, unknown>;
}

/** Reads the whole body chunk by chunk, as a client does, and splits it into events. */
async function readStream(response: Response) {
  if (response.body === null) {
    throw new Error("The response has no body to read.");
  }
  const reader = response.body.getReader();
  const decoder = new TextDecoder();
  let raw = "";
  for (;;) {
    const { done, value } = await reader.read();
    if (done) {
      break;
    }
    raw += decoder.decode(value, { stream: true });
  }
  const events: SseEvent[] = [];
  let heartbeats = 0;
  for (const block of raw.split(/\r?\n\r?\n/)) {
    const lines = block.split(/\r?\n/).filter((line) => line !== "");
    if (lines.length === 0) {
      continue;
    }
    if (lines.every((line) => line.startsWith(":"))) {
      heartbeats += lines.length;
      continue;
    }
    const event = lines.find((line) => line.startsWith("event: "))?.slice(7) ?? "message";
    const data = lines
      .filter((line) => line.startsWith("data: "))
      .map((line) => line.slice(6))
      .join("\n");
    events.push({ event, data: JSON.parse(data) as Record<string, unknown> });
  }
  return { events, heartbeats };
}

const names = (events: SseEvent[]) => events.map((item) => item.event);
const words = (events: SseEvent[]) =>
  events
    .filter((item) => item.event === "token")
    .map((item) => item.data.text as string)
    .join("");

/** One turn, as the app sends it: a stream is wanted, and a key makes a retry safe. */
const turn = (sessionId: string, body: object) =>
  fetch(`${API}/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
      Accept: "text/event-stream",
      "Idempotency-Key": "0b4e7a52-9c1d-4f38-a6b0-3d5e8f21c7a4",
    },
    body: JSON.stringify(body),
  });

async function call(path: string, init?: RequestInit) {
  const response = await fetch(`${API}${path}`, init);
  return { status: response.status, headers: response.headers, body: await response.json() };
}

const post = (path: string, body: object = {}) =>
  call(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });

describe("a streamed turn", () => {
  it("replays the opening: the coach speaks first, then done says where the interview stands", async () => {
    server.use(sseHandler("POST /api/v2/coach/sessions/s_01/messages", "coach/turn-01-start.sse"));

    const response = await turn("s_01", { language: "en" });
    const { events } = await readStream(response);

    expect(response.status).toBe(200);
    expect(response.headers.get("Content-Type")).toContain("text/event-stream");
    expect(new Set(names(events.slice(0, -1)))).toEqual(new Set(["token"]));
    expect(words(events)).toContain("Which country are you going to work in?");
    expect(events.at(-1)).toEqual({
      event: "done",
      data: {
        message_id: "m_001",
        stage: "intro",
        next_slot: "destination_country",
        turn_count: 0,
      },
    });
  });

  it("replays a fact, a heartbeat, the words, and the next question", async () => {
    server.use(sseHandler("POST /api/v2/coach/sessions/s_01/messages", "coach/turn-02-answer.sse"));

    const { events, heartbeats } = await readStream(
      await turn("s_01", { text: "Australia", language: "en" })
    );

    expect(names(events)[0]).toBe("slot_update");
    expect(events[0].data).toEqual({ slot: "destination_country", value: "AU", confirmed: true });
    expect(heartbeats).toBe(1);
    expect(words(events)).toContain("What kind of work will you do?");
    expect(events.at(-1)?.data).toMatchObject({
      stage: "intro",
      next_slot: "job_type",
      turn_count: 1,
    });
  });

  it("keeps Hindi and structured amounts whole", async () => {
    server.use(
      sseHandler("POST /api/v2/coach/sessions/s_02/messages", "coach/turn-03-answer-hindi.sse")
    );

    const { events } = await readStream(
      await turn("s_02", { text: "1,50,000 रुपये", language: "hi" })
    );

    expect(events[0].data).toEqual({
      slot: "recruitment_fee_paid",
      value: { amount: 150000, currency: "INR", period: "once" },
      confirmed: true,
    });
    expect(words(events)).toContain("कर्ज़ बाकी है");
  });

  it("can be a clarifying question: no fact stored, the same question still next", async () => {
    server.use(
      sseHandler("POST /api/v2/coach/sessions/s_02/messages", "coach/turn-04-clarify.sse")
    );

    const { events } = await readStream(
      await turn("s_02", { text: "मैंने 1,50,000 दिए", language: "hi" })
    );

    expect(names(events)).not.toContain("slot_update");
    expect(events.at(-1)?.data).toMatchObject({ next_slot: "recruitment_fee_paid" });
  });

  it("reaches the review with the words that GET returns as the last message", async () => {
    server.use(sseHandler("POST /api/v2/coach/sessions/s_03/messages", "coach/turn-05-review.sse"));

    const { events } = await readStream(
      await turn("s_03", { text: "I have a bank account", language: "en" })
    );
    const session = (await call("/sessions/s_03")).body;
    const last = session.messages.at(-1);

    expect(words(events)).toBe(last.text);
    expect(events.at(-1)?.data).toMatchObject({
      message_id: last.id,
      stage: "review",
      next_slot: null,
    });
    expect(session.score).toMatchObject({ total: 57, band: "getting_ready" });
  });

  it("may send the fact after the words, and a client must not mind", async () => {
    server.use(
      sseHandler("POST /api/v2/coach/sessions/s_01/messages", "coach/turn-06-late-slot-update.sse")
    );

    const { events } = await readStream(await turn("s_01", { text: "Care work", language: "en" }));

    expect(names(events)).toEqual(["token", "token", "token", "slot_update", "done"]);
  });

  it("can redirect an off-topic question and store nothing", async () => {
    server.use(
      sseHandler("POST /api/v2/coach/sessions/s_01/messages", "coach/turn-07-redirect.sse")
    );

    const { events } = await readStream(
      await turn("s_01", { text: "Which phone should I buy?", language: "en" })
    );

    expect(names(events)).not.toContain("slot_update");
    // The server's fixed words (backend guard_texts.REDIRECT["en"]), which do not repeat the
    // question: the mock shows what a worker really gets (D-225).
    expect(words(events)).toBe(
      "I can only help you plan your money before you leave. Please answer my last question when you are ready."
    );
    expect(events.at(-1)?.data).toMatchObject({ stage: "intro", next_slot: "destination_country" });
  });

  it("can repeat the current question in a new language when the request has no text", async () => {
    server.use(
      sseHandler("POST /api/v2/coach/sessions/s_02/messages", "coach/turn-08-language-switch.sse")
    );

    const { events } = await readStream(await turn("s_02", { language: "hi" }));

    expect(words(events)).toContain("एजेंट या रिक्रूटर");
    expect(events.at(-1)?.data).toMatchObject({ next_slot: "recruitment_fee_paid", turn_count: 6 });
  });

  it("ends with an error event after the words when the model times out", async () => {
    server.use(
      sseHandler("POST /api/v2/coach/sessions/s_01/messages", "coach/turn-error-midstream.sse")
    );

    const { events } = await readStream(await turn("s_01", { text: "Australia", language: "en" }));
    const last = events.at(-1);

    expect(names(events)).toEqual(["token", "token", "error"]);
    expect(last?.data).toMatchObject({ code: "ai_timeout" });
    expect(last?.data.request_id).toEqual(expect.any(String));
  });

  it("can stop with no done and no error: the connection dropped, so the client retries", async () => {
    server.use(
      sseHandler("POST /api/v2/coach/sessions/s_01/messages", "coach/turn-error-dropped.sse")
    );

    const { events } = await readStream(await turn("s_01", { text: "Australia", language: "en" }));

    expect(names(events)).not.toContain("done");
    expect(names(events)).not.toContain("error");
    expect(words(events)).toBe("Australia, thank you. What kind of");
  });
});

describe("a turn that is refused before the stream starts", () => {
  it.each([
    ["turn-error-session-not-active.json", "s_07", 409, "session_not_active"],
    ["turn-error-in-progress.json", "s_02", 409, "turn_in_progress"],
    ["turn-error-text-too-long.json", "s_01", 422, "validation_failed"],
    ["turn-error-rate-limited.json", "s_01", 429, "rate_limited"],
    ["turn-error-ai-busy.json", "s_01", 503, "ai_busy"],
  ])("can refuse with %s", async (name, sessionId, status, code) => {
    server.use(handlerForMock(`coach/${name}`));

    const response = await turn(sessionId, { text: "x", language: "en" });
    const body = await response.json();

    expect(response.status).toBe(status);
    expect(body.code).toBe(code);
    expect(body.request_id).toBe(response.headers.get("X-Request-ID"));
  });

  it("tells the screen how long to wait", async () => {
    server.use(handlerForMock("coach/turn-error-in-progress.json"));

    const response = await turn("s_02", { text: "x", language: "en" });

    expect(response.headers.get("Retry-After")).toBe("2");
  });
});

describe("the sessions", () => {
  it("starts a new one (201) and resumes the open one (200)", async () => {
    const created = await post("/sessions", { language: "en" });
    expect(created.status).toBe(201);
    expect(created.body).toMatchObject({
      resumed: false,
      stage: "intro",
      messages: [],
      score: null,
    });

    server.use(handlerForMock("coach/sessions-create-02-resumed.json"));
    const resumed = await post("/sessions", { language: "en" });
    expect(resumed.status).toBe(200);
    expect(resumed.body).toMatchObject({ resumed: true, language: "hi", stage: "debt" });
    expect(resumed.body.messages).toHaveLength(13);
  });

  it("gives each state: asking, the review, the three bands, completed", async () => {
    expect((await call("/sessions/s_02")).body.next_slot).toBe("recruitment_fee_paid");
    expect((await call("/sessions/s_03")).body.slots.monthly_salary.source).toBe(
      "contract_prefill"
    );

    const bands = await Promise.all(
      ["s_04", "s_05", "s_06"].map(async (id) => (await call(`/sessions/${id}`)).body.score.band)
    );
    expect(bands).toEqual(["getting_ready", "needs_work", "well_prepared"]);

    const completed = (await call("/sessions/s_07")).body;
    expect(completed).toMatchObject({ status: "completed", plan_id: PLAN_ID });
  });

  it("answers 404 for a session that is not there", async () => {
    const missing = await call("/sessions/s_missing");

    expect(missing.status).toBe(404);
    expect(missing.body.code).toBe("not_found");
  });
});

describe("the plan", () => {
  it("is made (201) with thirteen weeks and a provider quote", async () => {
    const { status, body } = await post("/sessions/s_04/plan", { language: "en" });

    expect(status).toBe(201);
    expect(body.id).toBe(PLAN_ID);
    expect(body.plan.weeks).toHaveLength(13);
    expect(body.plan.remittance.provider.name).toBe("Example Remit");
  });

  it("can have no debt and no quote", async () => {
    const { body } = await post("/sessions/s_06/plan", { language: "en" });

    expect(body.plan.debt).toBeNull();
    expect(body.plan.remittance).toMatchObject({ corridor_id: null, provider: null });
  });

  it("comes back (200) when it was made already", async () => {
    server.use(handlerForMock("coach/plan-03-already-exists.json"));

    const { status, body } = await post("/sessions/s_07/plan", { language: "en" });

    expect(status).toBe(200);
    expect(body.available_languages).toEqual(["en", "hi"]);
  });

  it.each([
    ["plan-error-not-ready.json", "s_02", 409, "plan_not_ready"],
    ["plan-error-in-progress.json", "s_04", 409, "request_in_progress"],
    ["plan-error-ai-bad-response.json", "s_04", 502, "ai_bad_response"],
  ])("can refuse with %s", async (name, sessionId, status, code) => {
    server.use(handlerForMock(`coach/${name}`));

    const result = await post(`/sessions/${sessionId}/plan`, { language: "en" });

    expect(result.status).toBe(status);
    expect(result.body.code).toBe(code);
  });

  it("is read in English by default and in Hindi on request, with the same figures", async () => {
    const english = (await call(`/plans/${PLAN_ID}`)).body;
    server.use(handlerForMock("coach/plan-get-02-hindi.json"));
    const hindi = (await call(`/plans/${PLAN_ID}?language=hi`)).body;

    expect(english.language).toBe("en");
    expect(hindi.language).toBe("hi");
    expect(hindi.plan.summary).not.toBe(english.plan.summary);
    expect(hindi.plan.monthly_budget).toEqual(english.plan.monthly_budget);
    expect(hindi.score).toEqual(english.score);
  });

  it("answers 404 for a plan that is not there", async () => {
    expect((await call("/plans/0123456789abcdef0123")).status).toBe(404);
  });
});

describe("the dashboard overview", () => {
  it("says Resume by default, and can say View plan, both, or Start", async () => {
    expect((await call("/overview")).body).toMatchObject({ session: { id: "s_02" }, plan: null });

    server.use(handlerForMock("coach/overview-02-plan-only.json"));
    expect((await call("/overview")).body).toMatchObject({ session: null, plan: { id: PLAN_ID } });

    server.use(handlerForMock("coach/overview-03-session-and-plan.json"));
    const both = (await call("/overview")).body;
    expect(both.session).not.toBeNull();
    expect(both.plan).not.toBeNull();

    server.use(handlerForMock("coach/overview-04-empty.json"));
    expect((await call("/overview")).body).toEqual({ session: null, plan: null });
  });
});
