import { streamCoachTurn, type StreamOptions } from "@/services/coachService";
import type {
  CoachDone,
  CoachFailure,
  CoachSlot,
  CoachStreamEvent,
  CoachTurnRequest,
} from "@/types/coach";
import { toFailure } from "@/utils/coachErrors";

export interface TurnHandlers {
  onToken: (text: string) => void;
  onSlotUpdate: (slot: CoachSlot, value: unknown) => void;
  /** Called before a retry: what the failed attempt showed is thrown away. */
  onReset: () => void;
}

export type TurnOutcome =
  | { kind: "done"; done: CoachDone }
  | { kind: "failed"; failure: CoachFailure }
  | { kind: "aborted" };

export interface TurnOptions {
  signal: AbortSignal;
  /** Waits in tests; unset, the real ones apply (a second after a drop, `Retry-After` otherwise). */
  retryDelayMs?: number;
  stream?: (request: CoachTurnRequest, options: StreamOptions) => AsyncIterable<CoachStreamEvent>;
  firstByteMs?: number;
  totalMs?: number;
}

const DROPPED_RETRY_MS = 1_000;
const DROPPED_RETRIES = 1;
const IN_PROGRESS_RETRIES = 3;
const IN_PROGRESS_DEFAULT_S = 2;
const IN_PROGRESS_MAX_S = 10;

function sleep(ms: number, signal: AbortSignal): Promise<void> {
  return new Promise((resolve) => {
    const timer = setTimeout(done, ms);
    function done() {
      clearTimeout(timer);
      signal.removeEventListener("abort", done);
      resolve();
    }
    signal.addEventListener("abort", done, { once: true });
  });
}

/**
 * Runs one turn to its end. A stream that dropped is tried once more at once, and a turn the
 * server says is still running is tried again after its `Retry-After`, always with the same
 * idempotency key, so a turn that did finish is replayed and never repeated (v2-coach.md).
 * Everything else is left to the worker's Try again button.
 */
export async function runCoachTurn(
  request: CoachTurnRequest,
  handlers: TurnHandlers,
  options: TurnOptions
): Promise<TurnOutcome> {
  const { signal, stream = streamCoachTurn, retryDelayMs } = options;
  let dropped = 0;
  let inProgress = 0;
  for (;;) {
    try {
      for await (const event of stream(request, {
        signal,
        firstByteMs: options.firstByteMs,
        totalMs: options.totalMs,
      })) {
        if (event.type === "token") {
          handlers.onToken(event.text);
        } else if (event.type === "slot_update") {
          handlers.onSlotUpdate(event.slot, event.value);
        } else if (event.type === "done") {
          return { kind: "done", done: event };
        } else {
          return { kind: "failed", failure: { code: event.code, status: 0 } };
        }
      }
      return { kind: "failed", failure: { code: "stream_dropped", status: 0 } };
    } catch (error) {
      if (signal.aborted) {
        return { kind: "aborted" };
      }
      const failure = toFailure(error);
      let wait: number | null = null;
      if (
        (failure.code === "stream_dropped" || failure.code === "stream_timeout") &&
        dropped < DROPPED_RETRIES
      ) {
        dropped += 1;
        wait = DROPPED_RETRY_MS;
      } else if (
        (failure.code === "request_in_progress" || failure.code === "turn_in_progress") &&
        inProgress < IN_PROGRESS_RETRIES
      ) {
        inProgress += 1;
        const seconds = failure.retryAfterSeconds ?? IN_PROGRESS_DEFAULT_S;
        wait = Math.min(seconds, IN_PROGRESS_MAX_S) * 1_000;
      }
      if (wait === null) {
        return { kind: "failed", failure };
      }
      handlers.onReset();
      await sleep(retryDelayMs ?? wait, signal);
      if (signal.aborted) {
        return { kind: "aborted" };
      }
    }
  }
}
