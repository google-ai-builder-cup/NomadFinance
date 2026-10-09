import { describe, expect, it, vi } from "vitest";

import { ApiError } from "@/services/apiClient";
import { CoachStreamDropped } from "@/services/coachService";
import type { CoachStreamEvent, CoachTurnRequest } from "@/types/coach";
import { runCoachTurn, type TurnHandlers } from "@/utils/coachTurnRunner";

const REQUEST: CoachTurnRequest = {
  sessionId: "s_01",
  text: "Australia",
  language: "en",
  idempotencyKey: "key-0000000000000001",
};

const DONE: CoachStreamEvent = {
  type: "done",
  messageId: "m_003",
  stage: "intro",
  nextSlot: "job_type",
  turnCount: 1,
};
const WORDS: CoachStreamEvent[] = [{ type: "token", text: "Thank you. " }];

/** One entry per attempt: the events the stream yields, then (unless it ends in `done` or an
 * error event) a drop; or an error to throw at once, as a refusal before the stream does. */
function streamOf(...attempts: Array<CoachStreamEvent[] | Error>) {
  const stream = vi.fn(async function* (_request: CoachTurnRequest) {
    const attempt = attempts[Math.min(stream.mock.calls.length - 1, attempts.length - 1)];
    if (attempt instanceof Error) {
      throw attempt;
    }
    for (const event of attempt) {
      yield event;
    }
    if (!attempt.some((event) => event.type === "done" || event.type === "error")) {
      throw new CoachStreamDropped("ended");
    }
  });
  return stream;
}

function handlers() {
  const calls: string[] = [];
  const value: TurnHandlers = {
    onToken: (text) => calls.push(`token:${text}`),
    onSlotUpdate: (slot, fact) => calls.push(`slot:${slot}=${String(fact)}`),
    onReset: () => calls.push("reset"),
  };
  return { calls, value };
}

const options = (stream: ReturnType<typeof streamOf>, signal = new AbortController().signal) => ({
  signal,
  stream,
  retryDelayMs: 0,
});

describe("runCoachTurn", () => {
  it("passes the words and the facts on, and ends with done", async () => {
    const { calls, value } = handlers();
    const stream = streamOf([
      { type: "slot_update", slot: "destination_country", value: "AU", confirmed: true },
      ...WORDS,
      DONE,
    ]);

    const outcome = await runCoachTurn(REQUEST, value, options(stream));

    expect(outcome).toMatchObject({ kind: "done", done: { messageId: "m_003" } });
    expect(calls).toEqual(["slot:destination_country=AU", "token:Thank you. "]);
  });

  it("does not retry an error event: nothing was saved, and the worker decides", async () => {
    const stream = streamOf([...WORDS, { type: "error", code: "ai_timeout", message: "" }]);

    const outcome = await runCoachTurn(REQUEST, handlers().value, options(stream));

    expect(outcome).toEqual({ kind: "failed", failure: { code: "ai_timeout", status: 0 } });
    expect(stream).toHaveBeenCalledTimes(1);
  });

  it("tries a dropped stream once more with the same request, and forgets what it showed", async () => {
    const { calls, value } = handlers();
    const stream = streamOf(WORDS, [...WORDS, DONE]);

    const outcome = await runCoachTurn(REQUEST, value, options(stream));

    expect(outcome.kind).toBe("done");
    expect(calls).toEqual(["token:Thank you. ", "reset", "token:Thank you. "]);
    // The same key both times: a turn the server did finish is replayed, not run twice.
    expect(stream.mock.calls.map(([request]) => request.idempotencyKey)).toEqual([
      REQUEST.idempotencyKey,
      REQUEST.idempotencyKey,
    ]);
  });

  it("gives up after the second drop", async () => {
    const stream = streamOf(WORDS);

    const outcome = await runCoachTurn(REQUEST, handlers().value, options(stream));

    expect(outcome).toEqual({ kind: "failed", failure: { code: "stream_dropped", status: 0 } });
    expect(stream).toHaveBeenCalledTimes(2);
  });

  it("treats a stalled stream like a dropped one", async () => {
    const stream = streamOf(new CoachStreamDropped("timeout"), [DONE]);

    const outcome = await runCoachTurn(REQUEST, handlers().value, options(stream));

    expect(outcome.kind).toBe("done");
    expect(stream).toHaveBeenCalledTimes(2);
  });

  it("waits and asks again while the server says the turn is still running, then gives up", async () => {
    const busy = new ApiError(409, "request_in_progress", 2);
    const stream = streamOf(busy);

    const outcome = await runCoachTurn(REQUEST, handlers().value, options(stream));

    expect(outcome).toMatchObject({ kind: "failed", failure: { code: "request_in_progress" } });
    // The first try and three more.
    expect(stream).toHaveBeenCalledTimes(4);
  });

  it("carries on when the running turn finishes in the meantime", async () => {
    const stream = streamOf(new ApiError(409, "turn_in_progress", 2), [...WORDS, DONE]);

    const outcome = await runCoachTurn(REQUEST, handlers().value, options(stream));

    expect(outcome.kind).toBe("done");
  });

  it("waits as long as Retry-After says, but never more than ten seconds", async () => {
    vi.useFakeTimers();
    try {
      const stream = streamOf(new ApiError(409, "request_in_progress", 600), [DONE]);
      const running = runCoachTurn(REQUEST, handlers().value, {
        signal: new AbortController().signal,
        stream,
      });

      await vi.advanceTimersByTimeAsync(9_999);
      expect(stream).toHaveBeenCalledTimes(1);
      await vi.advanceTimersByTimeAsync(1);
      expect((await running).kind).toBe("done");
    } finally {
      vi.useRealTimers();
    }
  });

  it.each([
    ["ai_busy", 503],
    ["rate_limited", 429],
    ["session_not_active", 409],
    ["validation_failed", 422],
  ])("hands %s back at once, without trying again", async (code, status) => {
    const stream = streamOf(new ApiError(status, code));

    const outcome = await runCoachTurn(REQUEST, handlers().value, options(stream));

    expect(outcome).toMatchObject({ kind: "failed", failure: { code, status } });
    expect(stream).toHaveBeenCalledTimes(1);
  });

  it("reports an abort as aborted, not as a failure", async () => {
    const controller = new AbortController();
    const stream = vi.fn(async function* () {
      controller.abort();
      yield* [] as CoachStreamEvent[];
      throw new Error("aborted");
    });

    const outcome = await runCoachTurn(REQUEST, handlers().value, {
      signal: controller.signal,
      stream,
      retryDelayMs: 0,
    });

    expect(outcome).toEqual({ kind: "aborted" });
  });

  it("stops waiting to retry when the worker leaves the screen", async () => {
    vi.useFakeTimers();
    try {
      const controller = new AbortController();
      const stream = streamOf(WORDS);
      const running = runCoachTurn(REQUEST, handlers().value, {
        signal: controller.signal,
        stream,
      });

      await vi.advanceTimersByTimeAsync(10);
      controller.abort();

      expect(await running).toEqual({ kind: "aborted" });
      expect(stream).toHaveBeenCalledTimes(1);
    } finally {
      vi.useRealTimers();
    }
  });
});
