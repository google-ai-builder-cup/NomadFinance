// Replays the Coach's turn route from docs/mocks/coach/ and records what the screen sent, for the
// tests of the chat (NF-FC-017). Only tests import this module; the app never does.
import { http, HttpResponse } from "msw";

import { jsonMocks, sseMocks } from "@/mocks/files";
import { server } from "@/mocks/server";
import type { CoachSessionStart } from "@/types/coach";

/** A recorded stream (`coach/turn-02-answer.sse`), a refusal (`{ refusal: "coach/turn-error-....json" }`)
 * or bytes of your own. */
export type TurnReply = string | { refusal: string } | { bytes: string };

export interface SentTurn {
  key: string | null;
  body: { text?: string; language?: string };
}

const STREAM_HEADERS = { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" };

function respond(reply: TurnReply): Response {
  if (typeof reply === "string") {
    const bytes = sseMocks.get(reply);
    if (bytes === undefined) {
      throw new Error(`No stream "${reply}" in docs/mocks/.`);
    }
    return new HttpResponse(bytes, { status: 200, headers: STREAM_HEADERS });
  }
  if ("bytes" in reply) {
    return new HttpResponse(reply.bytes, { status: 200, headers: STREAM_HEADERS });
  }
  const mock = jsonMocks.get(reply.refusal);
  if (mock?.status === undefined) {
    throw new Error(`No refusal "${reply.refusal}" in docs/mocks/.`);
  }
  return HttpResponse.json(mock.body as Record<string, unknown>, {
    status: mock.status,
    headers: mock.headers,
  });
}

/**
 * Answers the turns of any session in order, one reply each; the last one repeats if the screen
 * asks more often. Returns the list the screen's requests are recorded in.
 */
export function replayTurns(...replies: TurnReply[]): SentTurn[] {
  const sent: SentTurn[] = [];
  server.use(
    http.post("*/api/v2/coach/sessions/:id/messages", async ({ request }) => {
      const reply = replies[Math.min(sent.length, replies.length - 1)];
      sent.push({
        key: request.headers.get("Idempotency-Key"),
        body: (await request.json()) as SentTurn["body"],
      });
      return respond(reply);
    })
  );
  return sent;
}

/** A session mock's body, as the start route returns it, with fields changed for one test. */
export function sessionFrom(
  name: string,
  changes: Partial<CoachSessionStart> = {}
): CoachSessionStart {
  const mock = jsonMocks.get(name);
  if (mock?.body === undefined) {
    throw new Error(`No mock "${name}" in docs/mocks/.`);
  }
  const body = mock.body as Omit<CoachSessionStart, "resumed"> & { resumed?: boolean };
  return { ...body, resumed: body.resumed ?? false, ...changes };
}

/** Answers `GET /coach/sessions/{id}` with a session mock, as the score screen asks for it once the
 * answers are confirmed (NF-FC-020). Without `body` it is the mock as it is; `score: null` is the
 * answer while a rate is missing. */
export function replaySession(
  name = "coach/session-04-plan-mid.json",
  changes: Partial<CoachSessionStart> = {}
): { requests: number } {
  const seen = { requests: 0 };
  server.use(
    http.get("*/api/v2/coach/sessions/:id", () => {
      seen.requests += 1;
      return HttpResponse.json({ ...sessionFrom(name), ...changes });
    })
  );
  return seen;
}

export interface MadePlan {
  sent: { sessionId: string; language: string | undefined }[];
}

/** Answers `POST /coach/sessions/{id}/plan` with a plan mock, or a refusal (`{ refusal }`), and
 * records what was asked. `delayMs` keeps the answer back, to see the screen wait. */
export function replayPlan(
  reply: "coach/plan-01-created.json" | { refusal: string } = "coach/plan-01-created.json",
  delayMs = 0
): MadePlan {
  const made: MadePlan = { sent: [] };
  server.use(
    http.post("*/api/v2/coach/sessions/:id/plan", async ({ params, request }) => {
      const body = (await request.json()) as { language?: string };
      made.sent.push({ sessionId: String(params.id), language: body.language });
      if (delayMs > 0) {
        await new Promise((resolve) => setTimeout(resolve, delayMs));
      }
      const mock = jsonMocks.get(typeof reply === "string" ? reply : reply.refusal);
      if (mock === undefined) {
        throw new Error("No such plan mock in docs/mocks/.");
      }
      return HttpResponse.json(mock.body as Record<string, unknown>, {
        status: mock.status ?? 200,
        headers: mock.headers,
      });
    })
  );
  return made;
}

/** Answers `GET /coach/overview` with an overview mock (`coach/overview-04-empty.json` by default):
 * the Coach page asks for it to offer the way back to a plan (NF-FC-021). */
export function replayOverview(name = "coach/overview-04-empty.json"): void {
  const mock = jsonMocks.get(name);
  if (mock?.body === undefined) {
    throw new Error(`No mock "${name}" in docs/mocks/.`);
  }
  server.use(http.get("*/api/v2/coach/overview", () => HttpResponse.json(mock.body as object)));
}

export interface KeptAnswers {
  keep: string[];
}

/** Answers `POST /coach/sessions/{id}/known` with a mock (`coach/known-01-applied.json` by default)
 * or a refusal, and records which answers the worker kept (NF-FC-023). */
export function replayKnown(
  reply: "coach/known-01-applied.json" | { refusal: string } = "coach/known-01-applied.json"
): KeptAnswers[] {
  const sent: KeptAnswers[] = [];
  server.use(
    http.post("*/api/v2/coach/sessions/:id/known", async ({ request }) => {
      sent.push((await request.json()) as KeptAnswers);
      const mock = jsonMocks.get(typeof reply === "string" ? reply : reply.refusal);
      if (mock === undefined) {
        throw new Error("No such known mock in docs/mocks/.");
      }
      return HttpResponse.json(mock.body as Record<string, unknown>, {
        status: mock.status ?? 200,
        headers: mock.headers,
      });
    })
  );
  return sent;
}
