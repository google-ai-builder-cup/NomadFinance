import { useCallback, useEffect, useReducer, useRef } from "react";

import type { CoachSessionStart, CoachTurnRequest } from "@/types/coach";
import { chatReducer, initialChatState, isBusy } from "@/utils/coachChatState";
import { runCoachTurn, type TurnOptions } from "@/utils/coachTurnRunner";
import { newIdempotencyKey } from "@/utils/idempotency";

export type CoachChatTiming = Pick<
  TurnOptions,
  "retryDelayMs" | "firstByteMs" | "totalMs" | "stream"
>;

/**
 * The interview as the screen sees it: the lines, the reply that is arriving, where the interview
 * stands, and why the last turn failed. One turn runs at a time. The reply and the facts of a
 * turn are provisional until the server says `done`; a turn that fails shows neither.
 *
 * The coach speaks first: a session with no messages opens with a turn that has no text.
 */
export function useCoachChat(session: CoachSessionStart, timing: CoachChatTiming = {}) {
  const [state, dispatch] = useReducer(chatReducer, session, initialChatState);
  // Set while a turn runs, so it doubles as the "busy" flag and as the way to cancel it.
  const running = useRef<AbortController | null>(null);
  const last = useRef<CoachTurnRequest | null>(null);
  const lines = useRef(0);
  const timingRef = useRef(timing);
  useEffect(() => {
    timingRef.current = timing;
  });

  const execute = useCallback((request: CoachTurnRequest) => {
    const mine = new AbortController();
    running.current = mine;
    last.current = request;
    void runCoachTurn(
      request,
      {
        onToken: (text) => !mine.signal.aborted && dispatch({ type: "token", text }),
        onSlotUpdate: (slot, value) =>
          !mine.signal.aborted && dispatch({ type: "slot_update", slot, value }),
        onReset: () => !mine.signal.aborted && dispatch({ type: "stream_reset" }),
      },
      { signal: mine.signal, ...timingRef.current }
    ).then((outcome) => {
      // The screen was left, or another turn took over: nothing to show.
      if (outcome.kind === "aborted" || mine.signal.aborted) {
        return;
      }
      running.current = null;
      dispatch(
        outcome.kind === "done"
          ? { type: "done", done: outcome.done }
          : { type: "failed", failure: outcome.failure }
      );
    });
  }, []);

  /** Send the worker's answer; without text the coach speaks (the opening, or the question again). */
  const send = useCallback(
    (text?: string) => {
      if (running.current !== null) {
        return;
      }
      const clean = text?.trim() || undefined;
      lines.current += 1;
      dispatch({
        type: "turn_started",
        line: clean ? { id: `local-${lines.current}`, role: "user", text: clean } : null,
      });
      execute({
        sessionId: session.id,
        text: clean,
        language: session.language,
        idempotencyKey: newIdempotencyKey(),
      });
    },
    [execute, session.id, session.language]
  );

  /** Send the last turn again with the same key: if the server finished it, it is replayed. */
  const retry = useCallback(() => {
    if (running.current !== null || last.current === null) {
      return;
    }
    dispatch({ type: "retry_started" });
    execute(last.current);
  }, [execute]);

  useEffect(
    () => () => {
      running.current?.abort();
      running.current = null;
    },
    []
  );

  useEffect(() => {
    if (session.status === "active" && session.messages.length === 0) {
      send();
    }
    // Once, when the screen opens: a session with no messages gets its opening turn.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { state, busy: isBusy(state), send, retry };
}
