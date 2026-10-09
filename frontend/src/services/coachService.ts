import { ApiError, apiRequest } from "@/services/apiClient";
import {
  COACH_SLOTS,
  COACH_STAGES,
  type CoachSessionStart,
  type CoachSlot,
  type CoachStage,
  type CoachStreamEvent,
  type CoachTurnRequest,
} from "@/types/coach";
import type { LanguageCode } from "@/types/enums";
import { createSseParser, type SseFrame } from "@/utils/sse";

// docs/api/v2-coach.md, "Client rules": 30 s for the first byte (a heartbeat counts) and 60 s for
// the whole turn, then the stream is treated as dropped.
export const FIRST_BYTE_TIMEOUT_MS = 30_000;
export const TURN_TIMEOUT_MS = 60_000;

/** The stream broke, ended with neither `done` nor `error`, or went quiet for too long. */
export class CoachStreamDropped extends Error {
  constructor(readonly reason: "ended" | "timeout" | "network") {
    super(`The coach's stream was dropped (${reason}).`);
    this.name = "CoachStreamDropped";
  }
}

export interface StreamOptions {
  /** Cancelling it closes the connection, which also stops the upstream Gemini call. */
  signal?: AbortSignal;
  firstByteMs?: number;
  totalMs?: number;
}

/** Start the worker's interview, or get the one that is open. `restart` closes the open one. */
export async function startCoachSession(
  language: LanguageCode,
  restart = false
): Promise<CoachSessionStart> {
  const response = await apiRequest("/api/v2/coach/sessions", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ language, ...(restart && { restart: true }) }),
  });
  return (await response.json()) as CoachSessionStart;
}

function isObject(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function toEvent(frame: SseFrame): CoachStreamEvent | null {
  let data: unknown;
  try {
    data = JSON.parse(frame.data);
  } catch {
    throw new CoachStreamDropped("network");
  }
  if (!isObject(data)) {
    throw new CoachStreamDropped("network");
  }
  switch (frame.event) {
    case "token":
      return typeof data.text === "string" ? { type: "token", text: data.text } : null;
    case "slot_update":
      return COACH_SLOTS.includes(data.slot as CoachSlot)
        ? {
            type: "slot_update",
            slot: data.slot as CoachSlot,
            value: data.value,
            confirmed: data.confirmed === true,
          }
        : null;
    case "done":
      if (typeof data.message_id !== "string" || !COACH_STAGES.includes(data.stage as CoachStage)) {
        throw new CoachStreamDropped("network");
      }
      return {
        type: "done",
        messageId: data.message_id,
        stage: data.stage as CoachStage,
        nextSlot: (data.next_slot as CoachSlot | null) ?? null,
        turnCount: typeof data.turn_count === "number" ? data.turn_count : 0,
      };
    case "error":
      return {
        type: "error",
        code: typeof data.code === "string" ? data.code : "unknown",
        message: typeof data.message === "string" ? data.message : "",
      };
    // An event this version does not know is ignored: the contract may add some.
    default:
      return null;
  }
}

/**
 * One turn of the interview as a stream of events, ending after `done` or `error`. Read with
 * `fetch` and a stream reader, not `EventSource`: a turn is a POST with a token and a key.
 *
 * Throws `ApiError` for a refusal before the stream started, and `CoachStreamDropped` for a stream
 * that ended without a terminal event, so the caller can retry with the same idempotency key.
 * After `options.signal` is cancelled the call throws too, whatever the error is; the caller checks
 * the signal first and ignores it.
 */
export async function* streamCoachTurn(
  request: CoachTurnRequest,
  options: StreamOptions = {}
): AsyncGenerator<CoachStreamEvent> {
  const { signal, firstByteMs = FIRST_BYTE_TIMEOUT_MS, totalMs = TURN_TIMEOUT_MS } = options;
  const controller = new AbortController();
  let timedOut = false;
  const expire = () => {
    timedOut = true;
    controller.abort();
  };
  const cancel = () => controller.abort();
  const totalTimer = setTimeout(expire, totalMs);
  let firstByteTimer: ReturnType<typeof setTimeout> | undefined = setTimeout(expire, firstByteMs);
  signal?.addEventListener("abort", cancel, { once: true });
  if (signal?.aborted) {
    cancel();
  }
  // A read waits on the connection, which may not report the abort at once (or at all, for a
  // server that has simply gone quiet), so the read is raced against the abort itself.
  const stopped = new Promise<never>((_resolve, reject) => {
    const stop = () => reject(new DOMException("The stream was stopped.", "AbortError"));
    if (controller.signal.aborted) {
      stop();
    }
    controller.signal.addEventListener("abort", stop, { once: true });
  });
  stopped.catch(() => undefined);

  let reader: ReadableStreamDefaultReader<Uint8Array> | undefined;
  try {
    let response: Response;
    try {
      response = await apiRequest(
        `/api/v2/coach/sessions/${encodeURIComponent(request.sessionId)}/messages`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            Accept: "text/event-stream",
            "Idempotency-Key": request.idempotencyKey,
          },
          body: JSON.stringify({
            ...(request.text !== undefined && { text: request.text }),
            language: request.language,
          }),
          signal: controller.signal,
        }
      );
    } catch (error) {
      // apiClient reports any fetch failure as status 0; a spent timer is a stalled stream.
      if (timedOut && error instanceof ApiError && error.status === 0) {
        throw new CoachStreamDropped("timeout");
      }
      throw error;
    }
    if (response.body === null) {
      throw new CoachStreamDropped("ended");
    }

    reader = response.body.getReader();
    const decoder = new TextDecoder();
    const parser = createSseParser();
    for (;;) {
      let chunk: ReadableStreamReadResult<Uint8Array>;
      try {
        chunk = await Promise.race([reader.read(), stopped]);
      } catch (error) {
        if (signal?.aborted) {
          throw error;
        }
        throw new CoachStreamDropped(timedOut ? "timeout" : "network");
      }
      if (chunk.done) {
        throw new CoachStreamDropped("ended");
      }
      // Any byte, a heartbeat included, shows the connection is alive.
      clearTimeout(firstByteTimer);
      firstByteTimer = undefined;
      for (const frame of parser.push(decoder.decode(chunk.value, { stream: true }))) {
        const event = toEvent(frame);
        if (event === null) {
          continue;
        }
        yield event;
        if (event.type === "done" || event.type === "error") {
          return;
        }
      }
    }
  } finally {
    clearTimeout(totalTimer);
    clearTimeout(firstByteTimer);
    signal?.removeEventListener("abort", cancel);
    // Stop reading and let go of the connection; the server cancels its Gemini call on disconnect.
    void reader?.cancel().catch(() => undefined);
  }
}
