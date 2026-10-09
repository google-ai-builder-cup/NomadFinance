import { useCallback, useEffect, useReducer, useRef, useState } from "react";

import {
  claimEntry,
  prepareBackgroundSync,
  readEntry,
  releaseEntry,
  removeEntry,
} from "@/lib/coachOutboxStore";
import { keepForLater } from "@/services/coachOutboxService";
import type { CoachSession, CoachSessionStart, CoachTurnRequest } from "@/types/coach";
import type { LanguageCode } from "@/types/enums";
import { chatReducer, initialChatState, isBusy, type ChatLine } from "@/utils/coachChatState";
import { isExpired, shouldQueue, toRequest, wasSaved } from "@/utils/coachOutbox";
import { runCoachTurn, type TurnOptions } from "@/utils/coachTurnRunner";
import { newIdempotencyKey } from "@/utils/idempotency";

export type CoachChatTiming = Pick<
  TurnOptions,
  "retryDelayMs" | "firstByteMs" | "totalMs" | "stream"
> & {
  /** How soon to look again when the service worker is sending the waiting answer. */
  recheckMs?: number;
  /** How long to wait for the phone's storage before going on without it. */
  storageMs?: number;
  /** How long the screen-reader copy of a finished reply stays in the page. */
  announcementMs?: number;
};

// While an answer waits and the device says it is online (a connection that is "up" but carries
// nothing, a phone behind a login page), try it again this often. The browser's own "online" event
// covers a connection that really came back.
const RETRY_EVERY_MS = 15_000;
// Another sender (the service worker) holds the answer and is sending it: look again soon.
const BUSY_RECHECK_MS = 3_000;
// Storage that neither answers nor fails (a database another tab is holding) must not keep the
// worker waiting: after this the screen goes on without it.
const STORAGE_PATIENCE_MS = 3_000;
// A finished reply is also in a hidden region that is read out when it appears. Left there, a reader
// moving through the page line by line would meet the reply twice (D-238), so it is taken away.
const ANNOUNCEMENT_STAYS_MS = 4_000;

/** The result of `work`, or `fallback` if it has not finished in time. */
function within<T>(work: Promise<T>, fallback: T, ms = STORAGE_PATIENCE_MS): Promise<T> {
  return new Promise((resolve) => {
    const timer = setTimeout(() => resolve(fallback), ms);
    work.then(
      (value) => {
        clearTimeout(timer);
        resolve(value);
      },
      () => {
        clearTimeout(timer);
        resolve(fallback);
      }
    );
  });
}

/**
 * The interview as the screen sees it: the lines, the reply that is arriving, where the interview
 * stands, and why the last turn failed. One turn runs at a time. The reply and the facts of a
 * turn are provisional until the server says `done`; a turn that fails shows neither.
 *
 * The coach speaks first: a session with no messages opens with a turn that has no text. Not while
 * the worker has yet to answer what the Coach already knows (`session.known`): the opening waits
 * for `adoptKnown`, so the first question is one that is still open.
 *
 * `language` is the language the worker wants the coach in (the app's language). When it changes
 * while the interview is open, a turn with no text and the new language is sent once the current
 * turn is over: the server keeps the session, the answers and the stage, says that the
 * language changed, and asks the same question again in it.
 *
 * An answer that never reached the server because there was no connection is kept (NF-FC-019): it
 * shows as waiting, and is sent again, with the same key, when the connection returns. With a
 * `uid` it is also kept on the phone, so closing the tab does not lose it and the service worker
 * can send it with the app closed; the server runs the turn once whoever sends it.
 */
export function useCoachChat(
  session: CoachSessionStart,
  timing: CoachChatTiming = {},
  language: LanguageCode = session.language as LanguageCode,
  uid?: string
) {
  const [state, dispatch] = useReducer(chatReducer, session, initialChatState);
  // Set while a turn runs, so it doubles as the "busy" flag and as the way to cancel it.
  const running = useRef<AbortController | null>(null);
  const last = useRef<CoachTurnRequest | null>(null);
  const lines = useRef(0);
  // The language the coach is speaking: the one the screen opened in, then that of each turn sent.
  // A resumed interview that was last in another language is not switched on opening: the
  // worker's next answer is sent in the app's language, and the server carries on in it.
  const spoken = useRef<string>(language);
  const timingRef = useRef(timing);
  const turnCount = useRef(state.turnCount);
  // The key of the answer that is kept on the phone, if one is.
  const kept = useRef<string | null>(null);
  const sending = useRef(false);
  const recheck = useRef<number | undefined>(undefined);
  const deliverRef = useRef<() => Promise<void>>(async () => undefined);
  // A resumed interview first looks for an answer an earlier visit left waiting.
  const [restoring, setRestoring] = useState(uid !== undefined && session.messages.length > 0);
  useEffect(() => {
    timingRef.current = timing;
    turnCount.current = state.turnCount;
  });

  const execute = useCallback(
    (request: CoachTurnRequest) => {
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
      ).then(async (outcome) => {
        // The screen was left, or another turn took over: nothing to show.
        if (outcome.kind === "aborted" || mine.signal.aborted) {
          return;
        }
        const queue =
          outcome.kind === "failed" &&
          shouldQueue(request, outcome.failure, navigator.onLine !== false);
        if (uid !== undefined) {
          // Kept or let go before the screen moves on, so the worker's next move never races it.
          // If the storage fails or is slow, the answer still waits in this tab, which is all the
          // screen itself needs.
          if (queue) {
            kept.current = request.idempotencyKey;
            await within(
              keepForLater(request, uid, turnCount.current),
              undefined,
              timingRef.current.storageMs
            );
          } else if (kept.current === request.idempotencyKey) {
            kept.current = null;
            await within(removeEntry(request.sessionId), undefined, timingRef.current.storageMs);
          }
          if (mine.signal.aborted) {
            return;
          }
        }
        running.current = null;
        dispatch(
          queue
            ? { type: "queued" }
            : outcome.kind === "done"
              ? { type: "done", done: outcome.done }
              : { type: "failed", failure: outcome.failure }
        );
      });
    },
    [uid]
  );

  /** Send the worker's answer; without text the coach speaks (the opening, or the question again). */
  const send = useCallback(
    (text?: string) => {
      if (running.current !== null || state.queued || restoring) {
        return;
      }
      const clean = text?.trim() || undefined;
      lines.current += 1;
      spoken.current = language;
      dispatch({
        type: "turn_started",
        line: clean ? { id: `local-${lines.current}`, role: "user", text: clean } : null,
      });
      execute({
        sessionId: session.id,
        text: clean,
        language,
        idempotencyKey: newIdempotencyKey(),
      });
    },
    [execute, session.id, language, state.queued, restoring]
  );

  /** Send the waiting answer again, with the same key: if the server has it, it is replayed. */
  const deliver = useCallback(async () => {
    const request = last.current;
    if (request === null || running.current !== null || sending.current) {
      return;
    }
    sending.current = true;
    try {
      if (uid !== undefined && kept.current === request.idempotencyKey) {
        // The service worker may be sending it: only one of us takes it.
        const claim = await claimEntry(request.sessionId, "page");
        if (claim.status === "busy") {
          recheck.current = window.setTimeout(
            () => void deliverRef.current(),
            timingRef.current.recheckMs ?? BUSY_RECHECK_MS
          );
          return;
        }
        // "gone": the service worker sent it already. Asking again replays it.
      }
      if (running.current === null) {
        dispatch({ type: "retry_started" });
        execute(request);
      }
    } finally {
      sending.current = false;
    }
  }, [execute, uid]);
  useEffect(() => {
    deliverRef.current = deliver;
  });

  /** Send the last turn again with the same key: if the server finished it, it is replayed. */
  const retry = useCallback(() => {
    if (state.queued) {
      void deliver();
      return;
    }
    if (running.current !== null || last.current === null) {
      return;
    }
    dispatch({ type: "retry_started" });
    execute(last.current);
  }, [deliver, execute, state.queued]);

  // The connection came back, or the worker returned to the screen: send what is waiting.
  useEffect(() => {
    if (!state.queued) {
      return;
    }
    const tryNow = () => void deliver();
    const whenReturned = () => {
      if (document.visibilityState === "visible" && navigator.onLine !== false) {
        tryNow();
      }
    };
    const timer = window.setInterval(whenReturned, RETRY_EVERY_MS);
    window.addEventListener("online", tryNow);
    document.addEventListener("visibilitychange", whenReturned);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("online", tryNow);
      document.removeEventListener("visibilitychange", whenReturned);
    };
  }, [state.queued, deliver]);

  useEffect(
    () => () => {
      // Leaving mid-send: an answer this screen was sending is let go, so the next visit (or the
      // service worker) need not wait out the lease to take it.
      if (running.current !== null && kept.current !== null) {
        void releaseEntry(session.id);
      }
      running.current?.abort();
      running.current = null;
      window.clearTimeout(recheck.current);
    },
    // The interview does not change under a mounted screen (the page keys it by its id).
    // eslint-disable-next-line react-hooks/exhaustive-deps
    []
  );

  // Install the service worker while the connection is good, so it is there when it is not.
  useEffect(() => {
    if (uid !== undefined) {
      prepareBackgroundSync();
    }
  }, [uid]);

  // An answer an earlier visit left waiting (the tab was closed, or the page reloaded offline):
  // shown again as waiting and sent when the connection allows. One the server has already saved
  // (the service worker sent it) or that is too old is dropped; one the server refused is shown
  // as not sent, with its reason.
  useEffect(() => {
    if (uid === undefined || !restoring) {
      return;
    }
    let cancelled = false;
    void (async () => {
      const entry = await within(readEntry(session.id), undefined, timingRef.current.storageMs);
      if (cancelled) {
        return;
      }
      if (entry !== undefined && entry.uid === uid) {
        if (isExpired(entry, Date.now()) || wasSaved(entry, session.turn_count)) {
          await removeEntry(session.id);
        } else {
          const request = toRequest(entry);
          last.current = request;
          lines.current += 1;
          const refused = entry.rejected;
          const line: ChatLine = {
            id: `local-${lines.current}`,
            role: "user",
            text: entry.text,
            failed: refused !== null,
            queued: refused === null,
          };
          // The service worker names a refusal it has no code for by its status ("http_413").
          const status = Number(/^http_(\d+)$/.exec(refused ?? "")?.[1] ?? 0);
          dispatch({
            type: "restored",
            line,
            failure: refused === null ? null : { code: refused, status },
          });
          if (refused === null) {
            kept.current = request.idempotencyKey;
            if (navigator.onLine !== false) {
              void deliverRef.current();
            }
          } else {
            await removeEntry(session.id);
          }
        }
      }
      if (!cancelled) {
        setRestoring(false);
      }
    })();
    return () => {
      cancelled = true;
    };
    // Once, when the screen opens.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const busy = isBusy(state);

  useEffect(() => {
    if (state.announcement === "") {
      return undefined;
    }
    const timer = setTimeout(
      () => dispatch({ type: "announcement_read" }),
      timingRef.current.announcementMs ?? ANNOUNCEMENT_STAYS_MS
    );
    return () => clearTimeout(timer);
  }, [state.announcement]);

  /** The worker kept (or changed) what the Coach already knew: take the session the server made of
   * it, then let the coach speak first. */
  const adoptKnown = useCallback(
    (applied: CoachSession) => {
      dispatch({ type: "known_applied", session: applied });
      send();
    },
    [send]
  );
  // The worker changed the language (here or in the header) while the interview is open: once no
  // turn is running, the coach continues in the new one. Not while a turn fails or is retried:
  // that turn is sent again as it was, in the language it began in. Not while an answer waits.
  useEffect(() => {
    if (
      session.status === "active" &&
      state.lines.length > 0 &&
      !busy &&
      !state.queued &&
      !restoring &&
      state.failure === null &&
      spoken.current !== language
    ) {
      send();
    }
  }, [
    busy,
    language,
    restoring,
    send,
    session.status,
    state.failure,
    state.lines.length,
    state.queued,
  ]);

  useEffect(() => {
    if (session.status === "active" && session.messages.length === 0 && !session.known) {
      send();
    }
    // Once, when the screen opens: a session with no messages gets its opening turn.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return { state, busy, send, retry, restoring, adoptKnown };
}
