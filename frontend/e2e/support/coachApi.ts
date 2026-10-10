import { readFileSync } from "node:fs";
import path from "node:path";

import type { Page, Route } from "@playwright/test";

import { readMock } from "./mockApi";

// A stand-in for the Coach's routes, for the browser tests of the interview (NF-FC-025). It keeps
// one worker's session in memory, so a reload, a language switch and an answer sent after the
// connection came back all find the interview where it was, the way the real server holds it.
//
// What it is not: it does not read the worker's words. Whatever is sent fills the next question
// with the answer of the worked example in docs/mocks/coach/ (an Australian care worker sending
// money to India), and the test checks what the screen sent. Reading the words is the backend's
// job and is tested there (NF-FC-010, NF-FC-024). The plan, the score and the sessions are the
// mock files themselves, so a change to the contract reaches these tests too.

export const SLOT_ORDER = [
  "destination_country",
  "job_type",
  "departure_date",
  "monthly_salary",
  "dependents",
  "remittance_target",
  "recruitment_fee_paid",
  "debt_outstanding",
  "debt_interest",
  "savings",
  "bank_or_wallet",
] as const;
export type Slot = (typeof SLOT_ORDER)[number];

const STAGE_OF: Record<Slot, string> = {
  destination_country: "intro",
  job_type: "intro",
  departure_date: "intro",
  monthly_salary: "income",
  dependents: "obligations",
  remittance_target: "obligations",
  recruitment_fee_paid: "debt",
  debt_outstanding: "debt",
  debt_interest: "debt",
  savings: "savings",
  bank_or_wallet: "savings",
};

export const QUESTION: Record<Slot, string> = {
  destination_country: "Which country will you work in?",
  job_type: "What kind of work will you do?",
  departure_date: "When do you plan to leave?",
  monthly_salary: "How much will you be paid?",
  dependents: "How many people depend on you?",
  remittance_target: "How much do you want to send home?",
  recruitment_fee_paid: "How much did you pay your agent?",
  debt_outstanding: "How much do you still owe?",
  debt_interest: "What interest do you pay on that debt?",
  savings: "How much have you saved?",
  bank_or_wallet: "Do you have a bank account or a mobile wallet?",
};

// The coach answering in Hindi after a switch, from docs/mocks/coach/turn-08-language-switch.sse.
const HINDI_SWITCH = "ठीक है, अब मैं हिंदी में बात करूँगा। ";
const HINDI_QUESTION: Partial<Record<Slot, string>> = {
  recruitment_fee_paid:
    "आपने इस नौकरी के लिए एजेंट या रिक्रूटर को कितना पैसा दिया है, या कितना देना है? ",
  debt_outstanding: "क्या आप पर इस सफ़र के लिए अब भी कर्ज़ बाकी है? कितना? ",
};
const HINDI_DEFAULT = "कृपया अगले सवाल का जवाब दें। ";

const MADE_PLAN_ID = "5a202702c922fc9b4fcf";
// The smallest file a PDF reader accepts as a PDF; the tests check the file is saved, not drawn.
const PDF_BYTES = "%PDF-1.4\n1 0 obj<</Type/Catalog>>endobj\ntrailer<</Root 1 0 R>>\n%%EOF\n";

interface StoredSlot {
  value: unknown;
  confirmed: boolean;
  source: string;
}
interface StoredMessage {
  id: string;
  role: "user" | "coach";
  text: string;
  language: string;
  at: string;
}
interface Stored {
  id: string;
  status: "active" | "completed" | "abandoned";
  stage: string;
  language: string;
  slots: Partial<Record<Slot, StoredSlot>>;
  messages: StoredMessage[];
  next_slot: Slot | null;
  turn_count: number;
  plan_id: string | null;
  known?: { items: { slot: Slot; value: unknown; source: string; as_of: string | null }[] };
  created_at: string;
  last_active: string;
}

export interface CoachCall {
  method: string;
  path: string;
  query: URLSearchParams;
  /** The `Idempotency-Key` of a turn. */
  key: string | null;
  body: { text?: string; language?: string; keep?: string[]; restart?: boolean };
}

export interface FakeCoach {
  calls: CoachCall[];
  /** The turns the server took in (a turn that never arrived is not here). */
  turns(): CoachCall[];
  /** The interview as the server holds it. */
  session(): Stored;
  /** `true`: every call fails, as if the phone had no signal. `"turns"`: only the answers fail,
   * as when the server is reached but a turn cannot get through. */
  setOffline(offline: boolean | "turns"): void;
}

export interface CoachApiOptions {
  /** Start the first interview with answers the profile already gives (`known`). */
  offerKnown?: boolean;
}

/** The answers of the worked example, in the order of the interview. */
function answers(): Record<Slot, unknown> {
  const session = readMock("coach/session-04-plan-mid.json").body as {
    slots: Record<Slot, { value: unknown }>;
  };
  return Object.fromEntries(SLOT_ORDER.map((slot) => [slot, session.slots[slot].value])) as Record<
    Slot,
    unknown
  >;
}

function nowIso(): string {
  return new Date().toISOString();
}

/** Answers `/api/**` for the page like the Coach does. Anything not mocked is a 404. */
export async function coachApi(page: Page, options: CoachApiOptions = {}): Promise<FakeCoach> {
  const worked = answers();
  const scoreBody = readMock("coach/session-04-plan-mid.json").body as { score: unknown };
  const calls: CoachCall[] = [];
  const replays = new Map<string, string>();
  let current: Stored | null = null;
  let sessions = 0;
  let messageCount = 0;
  let planMade = false;
  let offline: boolean | "turns" = false;
  let offerKnown = options.offerKnown ?? false;

  const nextSlot = (s: Stored): Slot | null => SLOT_ORDER.find((slot) => !s.slots[slot]) ?? null;
  const settle = (s: Stored) => {
    if (s.status === "completed") {
      return;
    }
    if (s.stage === "plan") {
      s.next_slot = null;
      return;
    }
    s.next_slot = nextSlot(s);
    s.stage = s.next_slot === null ? "review" : STAGE_OF[s.next_slot];
  };
  const say = (s: Stored, role: "user" | "coach", text: string, language: string) => {
    messageCount += 1;
    const message = {
      id: `m_${String(messageCount).padStart(3, "0")}`,
      role,
      text,
      language,
      at: nowIso(),
    };
    s.messages.push(message);
    s.last_active = message.at;
    return message;
  };
  const view = (s: Stored) => ({
    ...s,
    score: s.stage === "review" || s.stage === "plan" ? scoreBody.score : null,
  });
  const json = (
    route: Route,
    status: number,
    body: unknown,
    headers: Record<string, string> = {}
  ) =>
    route.fulfill({
      status,
      headers: { "Content-Type": "application/json", ...headers },
      body: JSON.stringify(body),
    });

  function start(language: string, restart: boolean) {
    if (current && current.status === "active" && !restart) {
      return { status: 200, body: { ...view(current), resumed: true } };
    }
    if (current && restart) {
      current.status = "abandoned";
    }
    sessions += 1;
    const created = nowIso();
    current = {
      id: `s_e2e_${sessions}`,
      status: "active",
      stage: "intro",
      language,
      slots: {},
      messages: [],
      next_slot: "destination_country",
      turn_count: 0,
      plan_id: null,
      created_at: created,
      last_active: created,
    };
    if (offerKnown) {
      const offer = readMock("coach/sessions-create-03-known.json").body as {
        known: Stored["known"];
      };
      current.known = offer.known;
      offerKnown = false;
    }
    return { status: 201, body: { ...view(current), resumed: false } };
  }

  function keepKnown(s: Stored, keep: string[]) {
    for (const item of s.known?.items ?? []) {
      if (keep.includes(item.slot)) {
        s.slots[item.slot] = { value: item.value, confirmed: true, source: "profile_prefill" };
      }
    }
    delete s.known;
    settle(s);
  }

  // One turn: the worker's words fill the next question, the coach asks the one after, and the
  // last answer opens the review. Words at the review confirm it.
  function turn(s: Stored, body: CoachCall["body"]): string {
    const language = body.language ?? s.language;
    s.language = language;
    const events: string[] = [];
    const emit = (event: string, data: unknown) =>
      events.push(`event: ${event}\ndata: ${JSON.stringify(data)}\n\n`);
    let reply: string;
    if (body.text !== undefined) {
      say(s, "user", body.text, language);
      s.turn_count += 1;
      if (s.stage === "review") {
        for (const slot of SLOT_ORDER) {
          const stored = s.slots[slot];
          if (stored) {
            stored.confirmed = true;
          }
        }
        s.stage = "plan";
        s.next_slot = null;
        reply =
          "Thank you. Your answers are confirmed. You can see your score and make your plan now.";
      } else {
        const slot = s.next_slot;
        if (slot !== null) {
          s.slots[slot] = { value: worked[slot], confirmed: true, source: "user" };
          emit("slot_update", { slot, value: worked[slot], confirmed: true });
        }
        settle(s);
        if (s.next_slot === null) {
          reply =
            "Thank you. Here is what I understood. Is this right? Say yes, or tell me what to change.";
        } else if (language === "hi") {
          reply = `धन्यवाद। ${HINDI_QUESTION[s.next_slot] ?? HINDI_DEFAULT}`;
        } else {
          reply = `Thank you. ${QUESTION[s.next_slot]}`;
        }
      }
    } else {
      settle(s);
      const slot = s.next_slot;
      if (language === "hi" && slot !== null) {
        reply = HINDI_SWITCH + (HINDI_QUESTION[slot] ?? HINDI_DEFAULT);
      } else {
        reply = slot === null ? "Is this right?" : `Hello! ${QUESTION[slot]}`;
      }
    }
    for (const piece of reply.match(/[^.?!]+[.?!]?\s*/g) ?? [reply]) {
      emit("token", { text: piece });
    }
    const message = say(s, "coach", reply, language);
    emit("done", {
      message_id: message.id,
      stage: s.stage,
      next_slot: s.next_slot,
      turn_count: s.turn_count,
    });
    return events.join("");
  }

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const raw = request.postData() ?? "";
    const body = (raw === "" ? {} : JSON.parse(raw)) as CoachCall["body"];
    const key = request.headers()["idempotency-key"] ?? null;
    if (offline === true || (offline === "turns" && /\/messages$/.test(url.pathname))) {
      return route.abort("internetdisconnected");
    }
    calls.push({ method, path: url.pathname, query: url.searchParams, key, body });
    const p = url.pathname;

    if (method === "GET" && p === "/api/v2/flags") {
      return json(route, 200, readMock("flags/flags-coach-on.json").body);
    }
    if (method === "POST" && p === "/api/v2/coach/sessions") {
      const started = start(body.language ?? "en", body.restart === true);
      return json(route, started.status, started.body);
    }
    if (method === "GET" && p === "/api/v2/coach/overview") {
      return json(route, 200, {
        session: null,
        plan: planMade
          ? { id: MADE_PLAN_ID, created_at: nowIso(), score_total: 57, band: "getting_ready" }
          : null,
      });
    }
    const inSession = /^\/api\/v2\/coach\/sessions\/([^/]+)(\/[a-z]+)?$/.exec(p);
    if (inSession && current && inSession[1] === current.id) {
      const s = current;
      if (method === "GET" && !inSession[2]) {
        return json(route, 200, view(s));
      }
      if (method === "POST" && inSession[2] === "/known") {
        keepKnown(s, body.keep ?? []);
        return json(route, 200, view(s));
      }
      if (method === "POST" && inSession[2] === "/messages") {
        // The same key again is the same turn: the stream is replayed and nothing runs twice.
        const replay = key === null ? undefined : replays.get(key);
        const stream = replay ?? turn(s, body);
        if (key !== null) {
          replays.set(key, stream);
        }
        return route.fulfill({
          status: 200,
          headers: {
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            ...(replay === undefined ? {} : { "Idempotency-Replayed": "true" }),
          },
          body: stream,
        });
      }
      if (method === "POST" && inSession[2] === "/plan" && s.stage === "plan") {
        s.status = "completed";
        s.plan_id = MADE_PLAN_ID;
        planMade = true;
        return json(route, 201, readMock("coach/plan-01-created.json").body);
      }
    }
    if (method === "GET" && p === `/api/v2/coach/plans/${MADE_PLAN_ID}`) {
      const hindi = url.searchParams.get("language") === "hi";
      return json(
        route,
        200,
        readMock(hindi ? "coach/plan-get-02-hindi.json" : "coach/plan-get-01-english.json").body
      );
    }
    if (method === "GET" && p === `/api/v2/coach/plans/${MADE_PLAN_ID}.pdf`) {
      return route.fulfill({
        status: 200,
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": `attachment; filename="nomadfinance-plan-${url.searchParams.get("language") ?? "en"}.pdf"`,
        },
        body: PDF_BYTES,
      });
    }
    return json(route, 404, { code: "not_found", message: "Not mocked", request_id: "e2e" });
  });

  return {
    calls,
    turns: () => calls.filter((c) => c.method === "POST" && /\/messages$/.test(c.path)),
    session: () => {
      if (!current) {
        throw new Error("No interview has been started yet.");
      }
      return current;
    },
    setOffline: (value) => {
      offline = value;
    },
  };
}

/** A string of a Coach translation file (`src/i18n/coach/<language>.json`), by its dotted key, so
 * a test that has switched language does not hard-code the words. */
export function coachText(language: string, key: string): string {
  const file = path.resolve(process.cwd(), `src/i18n/coach/${language}.json`);
  let node: unknown = JSON.parse(readFileSync(file, "utf8"));
  for (const part of key.split(".")) {
    node = (node as Record<string, unknown>)[part];
  }
  if (typeof node !== "string") {
    throw new Error(`No string "${key}" in the ${language} coach translations.`);
  }
  return node;
}
