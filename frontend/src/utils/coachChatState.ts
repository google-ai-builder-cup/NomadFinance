import type {
  CoachDone,
  CoachFailure,
  CoachSessionStart,
  CoachSlot,
  CoachStage,
} from "@/types/coach";

export interface ChatLine {
  id: string;
  role: "user" | "coach";
  text: string;
  /** The turn this line started did not go through (nothing was saved). */
  failed?: boolean;
}

export interface ChatState {
  lines: ChatLine[];
  /** The coach's reply while it streams; null when no turn is running. */
  draft: string | null;
  /** The worker's line that started the running (or failed) turn; null for a turn without text. */
  turnLineId: string | null;
  /** Facts the server understood during this turn. Kept aside: they count only once `done` comes. */
  pendingSlots: Partial<Record<CoachSlot, unknown>>;
  stage: CoachStage;
  nextSlot: CoachSlot | null;
  turnCount: number;
  /** Answered slots by name, as bare values: the screen picks defaults from them. */
  slots: Partial<Record<CoachSlot, unknown>>;
  failure: CoachFailure | null;
  /** The last finished coach reply, handed to the screen reader once. */
  announcement: string;
}

export type ChatAction =
  | { type: "turn_started"; line: ChatLine | null }
  | { type: "token"; text: string }
  | { type: "slot_update"; slot: CoachSlot; value: unknown }
  | { type: "stream_reset" }
  | { type: "done"; done: CoachDone }
  | { type: "failed"; failure: CoachFailure }
  | { type: "retry_started" };

export function initialChatState(session: CoachSessionStart): ChatState {
  const slots: ChatState["slots"] = {};
  for (const [name, answer] of Object.entries(session.slots)) {
    slots[name as CoachSlot] = answer.value;
  }
  return {
    lines: session.messages.map(({ id, role, text }) => ({ id, role, text })),
    draft: null,
    turnLineId: null,
    pendingSlots: {},
    stage: session.stage,
    nextSlot: session.next_slot,
    turnCount: session.turn_count,
    slots,
    failure: null,
    announcement: "",
  };
}

/** Whether a turn is running: the request is out or the reply is arriving. */
export const isBusy = (state: ChatState): boolean => state.draft !== null;

export function chatReducer(state: ChatState, action: ChatAction): ChatState {
  switch (action.type) {
    case "turn_started":
      return {
        ...state,
        // A line that never reached the server is dropped when the worker moves on.
        lines: [
          ...state.lines.filter((line) => !line.failed),
          ...(action.line ? [action.line] : []),
        ],
        draft: "",
        turnLineId: action.line?.id ?? null,
        pendingSlots: {},
        failure: null,
        // Cleared so the next finished reply is read out even if its words are the same.
        announcement: "",
      };
    case "token":
      return { ...state, draft: (state.draft ?? "") + action.text };
    case "slot_update":
      return { ...state, pendingSlots: { ...state.pendingSlots, [action.slot]: action.value } };
    case "stream_reset":
      return { ...state, draft: "", pendingSlots: {} };
    case "done": {
      const text = state.draft ?? "";
      return {
        ...state,
        // The id is the server's: the same message GET /sessions/{id} returns next time.
        lines: text
          ? [...state.lines, { id: action.done.messageId, role: "coach", text }]
          : state.lines,
        draft: null,
        slots: { ...state.slots, ...state.pendingSlots },
        pendingSlots: {},
        stage: action.done.stage,
        nextSlot: action.done.nextSlot,
        turnCount: action.done.turnCount,
        announcement: text,
      };
    }
    case "failed":
      // The words and facts of a turn that did not finish are thrown away, never shown as final.
      return {
        ...state,
        lines: state.lines.map((line) =>
          line.id === state.turnLineId ? { ...line, failed: true } : line
        ),
        draft: null,
        pendingSlots: {},
        failure: action.failure,
      };
    case "retry_started":
      return {
        ...state,
        lines: state.lines.map((line) => (line.failed ? { ...line, failed: false } : line)),
        draft: "",
        pendingSlots: {},
        failure: null,
      };
  }
}
