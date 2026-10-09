// @vitest-environment jsdom
// The stream client against the recorded streams of docs/mocks/coach/ (NF-FC-017): the real
// apiClient, reader and parser run, and only the backend's bytes come from the mock files.
import { delay, http, HttpResponse } from "msw";
import { describe, expect, it, vi } from "vitest";

import { sseHandler } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";
import { ApiError } from "@/services/apiClient";
import {
  applyKnownDetails,
  CoachStreamDropped,
  startCoachSession,
  streamCoachTurn,
} from "@/services/coachService";
import type { CoachStreamEvent, CoachTurnRequest } from "@/types/coach";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

const REQUEST: CoachTurnRequest = {
  sessionId: "s_01",
  text: "Australia",
  language: "en",
  idempotencyKey: "0b4e7a52-9c1d-4f38-a6b0-3d5e8f21c7a4",
};
const LINE = "POST /api/v2/coach/sessions/s_01/messages";

async function collect(
  request: CoachTurnRequest,
  options?: Parameters<typeof streamCoachTurn>[1]
): Promise<CoachStreamEvent[]> {
  const events: CoachStreamEvent[] = [];
  for await (const event of streamCoachTurn(request, options)) {
    events.push(event);
  }
  return events;
}

const words = (events: CoachStreamEvent[]) =>
  events.map((event) => (event.type === "token" ? event.text : "")).join("");

describe("streamCoachTurn", () => {
  it("reads a fact, skips the heartbeat and ends with done", async () => {
    server.use(sseHandler(LINE, "coach/turn-02-answer.sse"));

    const events = await collect(REQUEST);

    expect(events.map((event) => event.type)).toEqual([
      "slot_update",
      "token",
      "token",
      "token",
      "done",
    ]);
    expect(events[0]).toEqual({
      type: "slot_update",
      slot: "destination_country",
      value: "AU",
      confirmed: true,
    });
    expect(words(events)).toContain("What kind of work will you do?");
    expect(events.at(-1)).toEqual({
      type: "done",
      messageId: "m_003",
      stage: "intro",
      nextSlot: "job_type",
      turnCount: 1,
    });
  });

  it("sends the token, the key, the text and the language the contract asks for", async () => {
    let seen: { headers: Headers; body: unknown } | null = null;
    const bytes =
      'event: done\ndata: {"message_id":"m_1","stage":"intro","next_slot":"job_type","turn_count":1}\n\n';
    server.use(
      http.post("*/api/v2/coach/sessions/s_01/messages", async ({ request }) => {
        seen = { headers: request.headers, body: await request.json() };
        return new HttpResponse(bytes, { headers: { "Content-Type": "text/event-stream" } });
      })
    );

    await collect(REQUEST);

    expect(seen).not.toBeNull();
    const { headers, body } = seen as unknown as { headers: Headers; body: unknown };
    expect(headers.get("Authorization")).toBe("Bearer test-token");
    expect(headers.get("Idempotency-Key")).toBe(REQUEST.idempotencyKey);
    expect(headers.get("Accept")).toBe("text/event-stream");
    expect(body).toEqual({ text: "Australia", language: "en" });
  });

  it("leaves `text` out when the coach is to speak first", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/v2/coach/sessions/s_01/messages", async ({ request }) => {
        body = await request.json();
        return new HttpResponse(
          'event: done\ndata: {"message_id":"m_1","stage":"intro","next_slot":"job_type","turn_count":0}\n\n',
          { headers: { "Content-Type": "text/event-stream" } }
        );
      })
    );

    await collect({ ...REQUEST, text: undefined, language: "hi" });

    expect(body).toEqual({ language: "hi" });
  });

  it("keeps Hindi words whole", async () => {
    server.use(
      sseHandler("POST /api/v2/coach/sessions/s_02/messages", "coach/turn-03-answer-hindi.sse")
    );

    const events = await collect({ ...REQUEST, sessionId: "s_02", language: "hi" });

    expect(words(events)).toContain("कर्ज़ बाकी है");
  });

  it("hands over an error event after the words, as the last thing", async () => {
    server.use(sseHandler(LINE, "coach/turn-error-midstream.sse"));

    const events = await collect(REQUEST);

    expect(events.map((event) => event.type)).toEqual(["token", "token", "error"]);
    expect(events.at(-1)).toMatchObject({ type: "error", code: "ai_timeout" });
  });

  it("throws CoachStreamDropped when the stream ends with neither done nor error", async () => {
    server.use(sseHandler(LINE, "coach/turn-error-dropped.sse"));
    const seen: CoachStreamEvent[] = [];

    await expect(
      (async () => {
        for await (const event of streamCoachTurn(REQUEST)) {
          seen.push(event);
        }
      })()
    ).rejects.toMatchObject({ name: "CoachStreamDropped", reason: "ended" });

    // The words did arrive; it is the caller that must not show them as final.
    expect(words(seen)).toBe("Australia, thank you. What kind of");
  });

  it("ignores an event it does not know", async () => {
    server.use(
      http.post(
        "*/api/v2/coach/sessions/s_01/messages",
        () =>
          new HttpResponse(
            'event: telemetry\ndata: {"x":1}\n\nevent: done\ndata: {"message_id":"m_1","stage":"intro","next_slot":"job_type","turn_count":1}\n\n',
            { headers: { "Content-Type": "text/event-stream" } }
          )
      )
    );

    expect((await collect(REQUEST)).map((event) => event.type)).toEqual(["done"]);
  });

  it("treats data that is not JSON as a broken stream", async () => {
    server.use(
      http.post(
        "*/api/v2/coach/sessions/s_01/messages",
        () =>
          new HttpResponse("event: token\ndata: not json\n\n", {
            headers: { "Content-Type": "text/event-stream" },
          })
      )
    );

    await expect(collect(REQUEST)).rejects.toBeInstanceOf(CoachStreamDropped);
  });

  it("throws ApiError with the code and Retry-After for a refusal before the stream", async () => {
    // The mock declares this refusal for s_02, so the default handler answers it.
    const error = await collect({ ...REQUEST, sessionId: "s_02" }).catch((caught) => caught);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 409, detail: "turn_in_progress", retryAfterSeconds: 2 });
  });

  it("gives up on a connection that never says anything, as dropped", async () => {
    server.use(
      http.post("*/api/v2/coach/sessions/s_01/messages", async () => {
        await delay("infinite");
        return new HttpResponse(null);
      })
    );

    await expect(collect(REQUEST, { firstByteMs: 40, totalMs: 5_000 })).rejects.toMatchObject({
      name: "CoachStreamDropped",
      reason: "timeout",
    });
  });

  it("gives up on a stream that starts and then goes quiet, as dropped", async () => {
    server.use(
      http.post("*/api/v2/coach/sessions/s_01/messages", () => {
        const encoder = new TextEncoder();
        return new HttpResponse(
          new ReadableStream({
            start(controller) {
              controller.enqueue(encoder.encode('event: token\ndata: {"text":"Hi"}\n\n'));
              // Never closes: the server stopped talking.
            },
          }),
          { headers: { "Content-Type": "text/event-stream" } }
        );
      })
    );
    const seen: CoachStreamEvent[] = [];

    await expect(
      (async () => {
        for await (const event of streamCoachTurn(REQUEST, { firstByteMs: 1_000, totalMs: 80 })) {
          seen.push(event);
        }
      })()
    ).rejects.toMatchObject({ name: "CoachStreamDropped", reason: "timeout" });
    expect(words(seen)).toBe("Hi");
  });

  it("stops when the caller cancels", async () => {
    server.use(
      http.post("*/api/v2/coach/sessions/s_01/messages", async () => {
        await delay("infinite");
        return new HttpResponse(null);
      })
    );
    const controller = new AbortController();

    const running = collect(REQUEST, { signal: controller.signal }).catch((caught) => caught);
    controller.abort();

    expect(await running).toBeInstanceOf(Error);
    expect(controller.signal.aborted).toBe(true);
  });
});

describe("startCoachSession", () => {
  it("starts a session in the language asked, and does not ask to restart", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/v2/coach/sessions", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: "s_01" }, { status: 201 });
      })
    );

    const session = await startCoachSession("hi");

    expect(session.id).toBe("s_01");
    expect(body).toEqual({ language: "hi" });
  });

  it("asks to close the open interview when restarting", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/v2/coach/sessions", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: "s_09" }, { status: 201 });
      })
    );

    await startCoachSession("en", true);

    expect(body).toEqual({ language: "en", restart: true });
  });

  it("gets the default answer of the mock: a new English session with no messages", async () => {
    const session = await startCoachSession("en");

    expect(session).toMatchObject({ id: "s_01", stage: "intro", resumed: false, messages: [] });
  });
});

describe("applyKnownDetails", () => {
  it("sends the kept slots and gets the session with them in it", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/v2/coach/sessions/:id/known", async ({ request, params }) => {
        body = { id: params.id, ...((await request.json()) as object) };
        return HttpResponse.json({ id: "s_08", stage: "intro", slots: {} });
      })
    );

    const session = await applyKnownDetails("s_08", ["job_type", "savings"]);

    expect(body).toEqual({ id: "s_08", keep: ["job_type", "savings"] });
    expect(session.id).toBe("s_08");
  });

  it("sends an empty list when the worker keeps nothing", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/v2/coach/sessions/:id/known", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json({ id: "s_08" });
      })
    );

    await applyKnownDetails("s_08", []);

    expect(body).toEqual({ keep: [] });
  });

  it("reads the default answer of the mock: six answers kept, the date is next", async () => {
    const session = await applyKnownDetails("s_08", []);

    expect(Object.keys(session.slots)).toHaveLength(6);
    expect(session).toMatchObject({ stage: "intro", next_slot: "departure_date" });
    expect(session.known).toBeUndefined();
  });

  it("throws the API's error for a session that has ended", async () => {
    server.use(
      http.post("*/api/v2/coach/sessions/:id/known", () =>
        HttpResponse.json({ code: "session_not_active", message: "x" }, { status: 409 })
      )
    );

    await expect(applyKnownDetails("s_08", [])).rejects.toMatchObject({
      status: 409,
      detail: "session_not_active",
    });
  });
});
