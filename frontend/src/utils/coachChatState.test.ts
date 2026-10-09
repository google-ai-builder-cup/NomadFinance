import { describe, expect, it } from "vitest";

import type { CoachSessionStart } from "@/types/coach";
import {
  chatReducer,
  initialChatState,
  isBusy,
  type ChatAction,
  type ChatState,
} from "@/utils/coachChatState";

const SESSION: CoachSessionStart = {
  id: "s_01",
  status: "active",
  stage: "intro",
  language: "en",
  slots: { destination_country: { value: "AU", confirmed: true, source: "user" } },
  messages: [
    {
      id: "m_001",
      role: "coach",
      text: "Which country?",
      language: "en",
      at: "2026-10-20T08:00:00Z",
    },
    { id: "m_002", role: "user", text: "Australia", language: "en", at: "2026-10-20T08:00:30Z" },
  ],
  next_slot: "job_type",
  turn_count: 1,
  score: null,
  plan_id: null,
  created_at: "2026-10-20T08:00:00Z",
  last_active: "2026-10-20T08:00:30Z",
  resumed: true,
};

const run = (state: ChatState, ...actions: ChatAction[]) => actions.reduce(chatReducer, state);
const DONE = {
  messageId: "m_003",
  stage: "intro",
  nextSlot: "departure_date",
  turnCount: 2,
} as const;

describe("initialChatState", () => {
  it("starts from the transcript, the stage and the answers of the session", () => {
    const state = initialChatState(SESSION);

    expect(state.lines.map((line) => line.text)).toEqual(["Which country?", "Australia"]);
    expect(state.stage).toBe("intro");
    expect(state.nextSlot).toBe("job_type");
    expect(state.slots).toEqual({ destination_country: "AU" });
    expect(isBusy(state)).toBe(false);
  });
});

describe("what the Coach already knew, kept by the worker", () => {
  it("brings the kept answers and the stage the server settled on, and adds no line", () => {
    const fresh: CoachSessionStart = {
      ...SESSION,
      messages: [],
      slots: {},
      turn_count: 0,
      next_slot: null,
    };
    const kept = {
      ...fresh,
      stage: "intro" as const,
      next_slot: "departure_date" as const,
      slots: {
        destination_country: { value: "SG", confirmed: true, source: "profile_prefill" as const },
        savings: {
          value: { amount: 1200, currency: "SGD", period: "once" },
          confirmed: true,
          source: "identity_prefill" as const,
        },
      },
    };

    const state = run(initialChatState(fresh), { type: "known_applied", session: kept });

    expect(state.slots).toEqual({
      destination_country: "SG",
      savings: { amount: 1200, currency: "SGD", period: "once" },
    });
    expect(state.nextSlot).toBe("departure_date");
    expect(state.lines).toEqual([]);
    expect(isBusy(state)).toBe(false);
  });
});

describe("the screen-reader copy of a reply", () => {
  it("is taken away once it was read, and the next reply is read again even in the same words", () => {
    const done = { ...DONE, messageId: "m_010" };
    const said = run(
      initialChatState(SESSION),
      { type: "turn_started", line: null },
      { type: "token", text: "Thank you." },
      { type: "done", done }
    );
    expect(said.announcement).toBe("Thank you.");

    const quiet = run(said, { type: "announcement_read" });
    expect(quiet.announcement).toBe("");
    // The log keeps the reply: only the hidden copy goes.
    expect(quiet.lines.at(-1)?.text).toBe("Thank you.");

    const again = run(
      quiet,
      { type: "turn_started", line: null },
      { type: "token", text: "Thank you." },
      { type: "done", done: { ...done, messageId: "m_011" } }
    );
    expect(again.announcement).toBe("Thank you.");
  });
});

describe("a turn that finishes", () => {
  it("shows the words as they come but changes nothing else until done", () => {
    const state = run(
      initialChatState(SESSION),
      { type: "turn_started", line: { id: "local-1", role: "user", text: "Care work" } },
      { type: "token", text: "Thank " },
      { type: "token", text: "you." },
      { type: "slot_update", slot: "job_type", value: "care_worker" }
    );

    expect(isBusy(state)).toBe(true);
    expect(state.draft).toBe("Thank you.");
    expect(state.lines.at(-1)).toMatchObject({ role: "user", text: "Care work" });
    // The fact and the stage wait for `done`.
    expect(state.slots).toEqual({ destination_country: "AU" });
    expect(state.nextSlot).toBe("job_type");
  });

  it("commits the reply, the facts and the stage together on done", () => {
    const state = run(
      initialChatState(SESSION),
      { type: "turn_started", line: { id: "local-1", role: "user", text: "Care work" } },
      { type: "token", text: "Thank you." },
      { type: "slot_update", slot: "job_type", value: "care_worker" },
      { type: "done", done: DONE }
    );

    expect(isBusy(state)).toBe(false);
    expect(state.lines.at(-1)).toEqual({ id: "m_003", role: "coach", text: "Thank you." });
    expect(state.slots).toEqual({ destination_country: "AU", job_type: "care_worker" });
    expect(state.nextSlot).toBe("departure_date");
    expect(state.turnCount).toBe(2);
    expect(state.announcement).toBe("Thank you.");
  });

  it("clears the announcement when the next turn starts, so a repeated reply is read again", () => {
    const first = run(
      initialChatState(SESSION),
      { type: "turn_started", line: null },
      { type: "token", text: "Same words." },
      { type: "done", done: DONE }
    );

    expect(first.announcement).toBe("Same words.");
    expect(chatReducer(first, { type: "turn_started", line: null }).announcement).toBe("");
  });
});

describe("a turn that fails", () => {
  const failed = run(
    initialChatState(SESSION),
    { type: "turn_started", line: { id: "local-1", role: "user", text: "Care work" } },
    { type: "token", text: "Thank you. Let me" },
    { type: "slot_update", slot: "job_type", value: "care_worker" },
    { type: "failed", failure: { code: "ai_timeout", status: 0 } }
  );

  it("throws the half reply and the facts away and marks the worker's line as not sent", () => {
    expect(isBusy(failed)).toBe(false);
    expect(failed.draft).toBeNull();
    expect(failed.lines.map((line) => line.text)).not.toContain("Thank you. Let me");
    expect(failed.lines.at(-1)).toMatchObject({ text: "Care work", failed: true });
    expect(failed.slots).toEqual({ destination_country: "AU" });
    expect(failed.failure).toEqual({ code: "ai_timeout", status: 0 });
  });

  it("does not mark an older line when the turn had no text of its own", () => {
    const opening = run(
      initialChatState(SESSION),
      { type: "turn_started", line: null },
      { type: "failed", failure: { code: "ai_busy", status: 503 } }
    );

    expect(opening.lines.some((line) => line.failed)).toBe(false);
  });

  it("starts again on retry, with the line back to normal and the failure gone", () => {
    const retrying = chatReducer(failed, { type: "retry_started" });

    expect(isBusy(retrying)).toBe(true);
    expect(retrying.failure).toBeNull();
    expect(retrying.lines.some((line) => line.failed)).toBe(false);
  });

  it("drops the unsent line when the worker sends something else", () => {
    const next = chatReducer(failed, {
      type: "turn_started",
      line: { id: "local-2", role: "user", text: "Factory work" },
    });

    expect(next.lines.map((line) => line.text)).toEqual([
      "Which country?",
      "Australia",
      "Factory work",
    ]);
  });
});

describe("a stream that dropped and is tried again", () => {
  it("starts the reply over, so the words are not shown twice", () => {
    const state = run(
      initialChatState(SESSION),
      { type: "turn_started", line: null },
      { type: "token", text: "Australia, thank you. " },
      { type: "slot_update", slot: "job_type", value: "care_worker" },
      { type: "stream_reset" },
      { type: "token", text: "Australia, thank you. " },
      { type: "done", done: DONE }
    );

    expect(state.lines.at(-1)?.text).toBe("Australia, thank you. ");
    expect(state.slots.job_type).toBeUndefined();
  });
});

describe("an answer waiting for a connection", () => {
  const sent = run(initialChatState(SESSION), {
    type: "turn_started",
    line: { id: "local-1", role: "user", text: "Care work" },
  });
  const queued = chatReducer(chatReducer(sent, { type: "token", text: "half" }), {
    type: "queued",
  });

  it("marks the worker's line as waiting, not as failed, and shows no failure", () => {
    expect(queued.queued).toBe(true);
    expect(queued.failure).toBeNull();
    expect(queued.lines.at(-1)).toMatchObject({ text: "Care work", queued: true, failed: false });
  });

  it("throws the half reply of the attempt away and is no longer busy", () => {
    expect(isBusy(queued)).toBe(false);
    expect(queued.draft).toBeNull();
    expect(queued.lines.map((line) => line.text)).not.toContain("half");
  });

  it("goes back to a running turn when it is sent again", () => {
    const again = chatReducer(queued, { type: "retry_started" });

    expect(again.queued).toBe(false);
    expect(isBusy(again)).toBe(true);
    expect(again.lines.at(-1)).toMatchObject({ text: "Care work", queued: false });
  });

  it("is over when the server finishes the turn", () => {
    const done = run(
      queued,
      { type: "retry_started" },
      { type: "token", text: "Thanks." },
      {
        type: "done",
        done: DONE,
      }
    );

    expect(done.queued).toBe(false);
    expect(done.lines.map((line) => line.text)).toEqual([
      "Which country?",
      "Australia",
      "Care work",
      "Thanks.",
    ]);
  });
});

describe("an answer kept by an earlier visit", () => {
  const line = { id: "local-1", role: "user", text: "4200 AUD per month" } as const;

  it("comes back as a waiting line after the transcript", () => {
    const state = chatReducer(initialChatState(SESSION), {
      type: "restored",
      line: { ...line, queued: true },
      failure: null,
    });

    expect(state.queued).toBe(true);
    expect(state.lines.at(-1)).toMatchObject({ text: "4200 AUD per month", queued: true });
    expect(state.lines).toHaveLength(3);
  });

  it("comes back as not sent, with the reason, when the server refused it", () => {
    const state = chatReducer(initialChatState(SESSION), {
      type: "restored",
      line: { ...line, failed: true },
      failure: { code: "session_not_active", status: 409 },
    });

    expect(state.queued).toBe(false);
    expect(state.failure).toEqual({ code: "session_not_active", status: 409 });
    expect(state.lines.at(-1)).toMatchObject({ failed: true });
  });
});
