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
