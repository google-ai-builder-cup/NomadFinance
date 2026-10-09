// @vitest-environment jsdom
// What the Coach already knows (NF-FC-023): the card before the first question, keeping and
// changing its rows, and the interview that then asks only what is left.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import CoachChat from "@/components/coach/CoachChat";
import { loadNamespace } from "@/lib/i18n";
import { replayKnown, replayTurns, sessionFrom } from "@/mocks/coachTurns";
import { setupMockServer } from "@/mocks/server";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(cleanup);

const ALL_SIX = [
  "destination_country",
  "job_type",
  "monthly_salary",
  "remittance_target",
  "savings",
  "bank_or_wallet",
];
// The coach's opening once the six answers are in: the first open question is the leaving date.
const OPENING = {
  bytes:
    'event: token\ndata: {"text":"Hello. When will you leave?"}\n\n' +
    'event: done\ndata: {"message_id":"m_001","stage":"intro","next_slot":"departure_date","turn_count":0}\n\n',
};

function renderChat(onRestart = vi.fn()) {
  render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <CoachChat
          session={sessionFrom("coach/sessions-create-03-known.json")}
          onRestart={onRestart}
          timing={{ retryDelayMs: 0 }}
        />
      </MemoryRouter>
    </QueryClientProvider>
  );
  return { onRestart };
}

const card = () => screen.getByRole("region", { name: "What we already know" });

describe("the card of what the Coach already knows", () => {
  it("shows each answer with where it came from, before any question", () => {
    replayTurns(OPENING);
    renderChat();

    const rows = within(card()).getAllByRole("row").slice(1);
    expect(rows).toHaveLength(6);
    expect(within(rows[0] as HTMLElement).getByRole("cell", { name: /Singapore/ })).toBeTruthy();
    expect(within(rows[0] as HTMLElement).getByText("From your profile")).toBeTruthy();
    expect(within(rows[2] as HTMLElement).getByText("650 SGD per month")).toBeTruthy();
    expect(
      within(rows[2] as HTMLElement).getByText("Last salary you logged, September 25, 2026")
    ).toBeTruthy();
    expect(within(rows[3] as HTMLElement).getByText("500 SGD per month")).toBeTruthy();
    expect(within(rows[4] as HTMLElement).getByText("1,200 SGD")).toBeTruthy();
    expect(screen.getByText(/Your profile and your records stay as they are/)).toBeTruthy();
  });

  it("does not open the interview until the worker has answered it", async () => {
    const sent = replayTurns(OPENING);
    renderChat();

    await new Promise((resolve) => setTimeout(resolve, 50));

    expect(sent).toEqual([]);
    expect(screen.queryByRole("log")).toBeNull();
    expect(screen.queryByRole("group", { name: "Your answer" })).toBeNull();
  });

  it("keeps everything with one tap, then the coach asks the first open question", async () => {
    const kept = replayKnown();
    const sent = replayTurns(OPENING);
    const user = userEvent.setup();
    renderChat();

    await user.click(screen.getByRole("button", { name: "Use these answers" }));

    await within(await screen.findByRole("log")).findByText("Hello. When will you leave?");
    expect(kept).toEqual([{ keep: ALL_SIX }]);
    // The opening has no text: the coach speaks first, and the card is gone.
    expect(sent).toHaveLength(1);
    expect(sent[0]?.body.text).toBeUndefined();
    expect(screen.queryByRole("region", { name: "What we already know" })).toBeNull();
    // The answer box is for the date, the question that is still open.
    expect(screen.getByLabelText("Departure date")).toBeTruthy();
  });

  it("drops a row marked Change, and that one is asked as usual", async () => {
    const kept = replayKnown();
    replayTurns(OPENING);
    const user = userEvent.setup();
    renderChat();

    await user.click(within(card()).getByRole("button", { name: "Change: Your pay" }));
    const row = within(card()).getAllByRole("row")[3] as HTMLElement;
    expect(within(row).getByText("I will ask you this")).toBeTruthy();
    expect(within(row).queryByText("650 SGD per month")).toBeNull();
    await user.click(screen.getByRole("button", { name: "Use these answers" }));

    await screen.findByRole("log");
    expect(kept[0]?.keep).toEqual(ALL_SIX.filter((slot) => slot !== "monthly_salary"));
  });

  it("lets a dropped row be kept again", async () => {
    const kept = replayKnown();
    replayTurns(OPENING);
    const user = userEvent.setup();
    renderChat();
    await user.click(within(card()).getByRole("button", { name: "Change: Your pay" }));

    await user.click(within(card()).getByRole("button", { name: "Keep: Your pay" }));
    await user.click(screen.getByRole("button", { name: "Use these answers" }));

    await screen.findByRole("log");
    expect(kept[0]?.keep).toEqual(ALL_SIX);
  });

  it("with every row changed, offers only to ask every question", async () => {
    const kept = replayKnown();
    replayTurns(OPENING);
    const user = userEvent.setup();
    renderChat();

    for (const button of within(card()).getAllByRole("button", { name: /^Change: / })) {
      await user.click(button);
    }

    expect(
      (screen.getByRole("button", { name: "Use these answers" }) as HTMLButtonElement).disabled
    ).toBe(true);
    expect(screen.getByText(/I will ask each question/)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Ask me every question" }));
    await screen.findByRole("log");
    expect(kept).toEqual([{ keep: [] }]);
  });

  it("says so and lets the worker try again when it could not be saved", async () => {
    const kept = replayKnown({ refusal: "coach/known-error-unknown-slot.json" });
    replayTurns(OPENING);
    const user = userEvent.setup();
    renderChat();

    await user.click(screen.getByRole("button", { name: "Ask me every question" }));

    await screen.findByRole("alert");
    // Still the card, so nothing the worker chose is lost; Try again repeats the last choice.
    expect(card()).toBeTruthy();
    expect(kept).toEqual([{ keep: [] }]);
  });

  it("offers a new interview when the session has ended", async () => {
    replayKnown({ refusal: "coach/turn-error-session-not-active.json" });
    const user = userEvent.setup();
    const { onRestart } = renderChat();

    await user.click(screen.getByRole("button", { name: "Use these answers" }));

    const alert = await screen.findByRole("alert");
    await user.click(within(alert).getByRole("button", { name: "Start a new interview" }));
    await waitFor(() => expect(onRestart).toHaveBeenCalledTimes(1));
  });
});
