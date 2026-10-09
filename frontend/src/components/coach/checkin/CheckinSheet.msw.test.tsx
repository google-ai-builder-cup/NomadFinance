// @vitest-environment jsdom
// The check-in sheet against the mock API (NF-FC-022): three closed questions, one at a time, sent
// once to the plan and milestone of the reminder's link.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import CheckinSheet from "@/components/coach/checkin/CheckinSheet";
import { loadNamespace, setLanguage } from "@/lib/i18n";
import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";

const markRead = vi.hoisted(() => vi.fn(async () => undefined));

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { uid: "worker-1" }, loading: false }),
}));
vi.mock("@/services/notificationService", () => ({ markNotificationRead: markRead }));

setupMockServer();

const PLAN_ID = "5a202702c922fc9b4fcf";
const URL_D30 = `PUT /api/v2/coach/plans/${PLAN_ID}/checkins/d30`;

beforeAll(async () => {
  await loadNamespace("coach");
});
beforeEach(() => markRead.mockClear());
afterEach(async () => {
  cleanup();
  await setLanguage("en");
});

function renderSheet(milestone: "d30" | "d60" | "d90" = "d30") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <CheckinSheet planId={PLAN_ID} milestone={milestone} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

/** Records the answers the sheet sends, and answers with the first mock. */
function recordSends(): { milestone: string; body: unknown }[] {
  const sent: { milestone: string; body: unknown }[] = [];
  server.use(
    http.put("*/api/v2/coach/plans/:id/checkins/:milestone", async ({ params, request }) => {
      sent.push({ milestone: String(params.milestone), body: await request.json() });
      return HttpResponse.json({
        plan_id: params.id,
        milestone: params.milestone,
        answers: { remittance: "on_track", savings: "behind", pay: "full_on_time" },
        answered_at: "2026-12-31T09:12:40Z",
        already_answered: false,
      });
    })
  );
  return sent;
}

const choose = (user: ReturnType<typeof userEvent.setup>, name: string | RegExp) =>
  user.click(screen.getByRole("radio", { name }));
const press = (user: ReturnType<typeof userEvent.setup>, name: string | RegExp) =>
  user.click(screen.getByRole("button", { name }));

describe("the questions", () => {
  it("are asked one at a time, in order, with the progress said and the choice required", async () => {
    const user = userEvent.setup();
    renderSheet();

    expect(screen.getByText("Question 1 of 3")).toBeTruthy();
    const first = screen.getByRole("group", { name: "Did you send money home as in your plan?" });
    expect(
      within(first)
        .getAllByRole("radio")
        .map((r) => r.getAttribute("value"))
    ).toEqual(["on_track", "behind", "not_yet"]);
    expect((screen.getByRole("button", { name: "Next" }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByRole("button", { name: "Back" })).toBeNull();

    await choose(user, "Yes, as in my plan");
    await press(user, "Next");

    expect(screen.getByText("Question 2 of 3")).toBeTruthy();
    expect(screen.getByRole("group", { name: "Did you save money as in your plan?" })).toBeTruthy();
    expect(screen.getByRole("radio", { name: "I saved less than planned" })).toBeTruthy();
    // The next question starts with nothing chosen, and the reader is moved to its start.
    expect((screen.getByRole("button", { name: "Next" }) as HTMLButtonElement).disabled).toBe(true);
    expect(document.activeElement?.tagName).toBe("LEGEND");

    await choose(user, "Not yet");
    await press(user, "Next");

    expect(screen.getByText("Question 3 of 3")).toBeTruthy();
    expect(screen.getByRole("radio", { name: "I have not been paid" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Send my answers" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Next" })).toBeNull();
  });

  it("keep what was chosen when the worker goes back", async () => {
    const user = userEvent.setup();
    renderSheet();
    await choose(user, "I sent less than planned");
    await press(user, "Next");

    await press(user, "Back");

    expect(screen.getByText("Question 1 of 3")).toBeTruthy();
    expect(
      (screen.getByRole("radio", { name: "I sent less than planned" }) as HTMLInputElement).checked
    ).toBe(true);
  });

  it("are asked in the language of the app", async () => {
    await setLanguage("hi");
    renderSheet();

    expect(screen.getByText("सवाल 1 / 3")).toBeTruthy();
    expect(
      screen.getByRole("group", { name: "क्या आपने अपनी योजना के अनुसार घर पैसे भेजे?" })
    ).toBeTruthy();
  });
});

describe("sending the answers", () => {
  it("sends the three choices once, to the plan and milestone of the link, and thanks the worker", async () => {
    const sent = recordSends();
    const user = userEvent.setup();
    renderSheet("d60");

    await choose(user, "Yes, as in my plan");
    await press(user, "Next");
    await choose(user, "I saved less than planned");
    await press(user, "Next");
    await choose(user, "Yes, in full and on time");
    await press(user, "Send my answers");

    expect(await screen.findByText("Thank you")).toBeTruthy();
    expect(sent).toEqual([
      {
        milestone: "d60",
        body: { answers: { remittance: "on_track", savings: "behind", pay: "full_on_time" } },
      },
    ]);
    expect(screen.getByText("Your answers are saved.")).toBeTruthy();
    // The reminder is marked read, by the id the backend wrote it under.
    expect(markRead).toHaveBeenCalledWith("worker-1", `coach_checkin_${PLAN_ID}_d60`);
    // A plan that is behind points back to the plan; nothing points to a report when pay is fine.
    expect(screen.getByRole("link", { name: "View my plan" }).getAttribute("href")).toBe(
      `/coach/plan/${PLAN_ID}`
    );
    expect(screen.queryByRole("link", { name: "Report an employer" })).toBeNull();
    expect(screen.getByRole("link", { name: "Back to home" }).getAttribute("href")).toBe(
      "/dashboard"
    );
    // A second send is not possible from the thank-you.
    expect(screen.queryByRole("button", { name: "Send my answers" })).toBeNull();
  });

  it("thanks the worker even when the feed's mark-as-read never finishes", async () => {
    // Firestore keeps a write until the server has it; the thank-you must not wait for that.
    markRead.mockImplementationOnce(() => new Promise<undefined>(() => undefined));
    recordSends();
    const user = userEvent.setup();
    renderSheet();

    await choose(user, "Yes, as in my plan");
    await press(user, "Next");
    await choose(user, "Yes, as in my plan");
    await press(user, "Next");
    await choose(user, "Yes, in full and on time");
    await press(user, "Send my answers");

    expect(await screen.findByText("Thank you")).toBeTruthy();
    expect(markRead).toHaveBeenCalledOnce();
  });

  it("points a pay problem at the report page", async () => {
    server.use(
      http.put("*/api/v2/coach/plans/:id/checkins/:milestone", () =>
        HttpResponse.json({
          plan_id: PLAN_ID,
          milestone: "d30",
          answers: { remittance: "on_track", savings: "on_track", pay: "not_paid" },
          answered_at: "2026-12-31T09:12:40Z",
          already_answered: false,
        })
      )
    );
    const user = userEvent.setup();
    renderSheet();

    await choose(user, "Yes, as in my plan");
    await press(user, "Next");
    await choose(user, "Yes, as in my plan");
    await press(user, "Next");
    await choose(user, "I have not been paid");
    await press(user, "Send my answers");

    expect(
      (await screen.findByRole("link", { name: "Report an employer" })).getAttribute("href")
    ).toBe("/radar/report");
    // Everything on plan, so no nudge to look at the plan again.
    expect(screen.queryByRole("link", { name: "View my plan" })).toBeNull();
  });

  it("says so when the milestone was answered before, and shows the first answers' follow-up", async () => {
    server.use(handlerForMock("coach/checkin-02-already-answered.json"));
    const user = userEvent.setup();
    renderSheet();

    await choose(user, "I sent less than planned");
    await press(user, "Next");
    await choose(user, "Not yet");
    await press(user, "Next");
    await choose(user, "I have not been paid");
    await press(user, "Send my answers");

    expect(
      await screen.findByText("You already answered this check-in. Your first answers are kept.")
    ).toBeTruthy();
    // What is shown follows the stored answers (savings behind in the mock), not the new ones.
    expect(screen.getByRole("link", { name: "View my plan" })).toBeTruthy();
    expect(screen.queryByRole("link", { name: "Report an employer" })).toBeNull();
  });

  it("keeps the answers and says why when the check-in is not open yet", async () => {
    server.use(handlerForMock("coach/checkin-error-not-due.json", URL_D30));
    const user = userEvent.setup();
    renderSheet();
    await choose(user, "Yes, as in my plan");
    await press(user, "Next");
    await choose(user, "Yes, as in my plan");
    await press(user, "Next");
    await choose(user, "Yes, in full and on time");

    await press(user, "Send my answers");

    expect((await screen.findByRole("alert")).textContent).toBe(
      "This check-in is not open yet. We will remind you on the day."
    );
    expect(screen.queryByText("Thank you")).toBeNull();
    expect(
      (screen.getByRole("radio", { name: "Yes, in full and on time" }) as HTMLInputElement).checked
    ).toBe(true);
    expect(markRead).not.toHaveBeenCalled();
  });

  it("sends the same answers again after a server problem, with one tap", async () => {
    let calls = 0;
    const bodies: unknown[] = [];
    server.use(
      http.put("*/api/v2/coach/plans/:id/checkins/:milestone", async ({ request }) => {
        calls += 1;
        bodies.push(await request.json());
        return calls === 1
          ? HttpResponse.json({ code: "internal_error" }, { status: 500 })
          : HttpResponse.json({
              plan_id: PLAN_ID,
              milestone: "d30",
              answers: { remittance: "on_track", savings: "on_track", pay: "full_on_time" },
              answered_at: "2026-12-31T09:12:40Z",
              already_answered: false,
            });
      })
    );
    const user = userEvent.setup();
    renderSheet();
    await choose(user, "Yes, as in my plan");
    await press(user, "Next");
    await choose(user, "Yes, as in my plan");
    await press(user, "Next");
    await choose(user, "Yes, in full and on time");
    await press(user, "Send my answers");
    expect((await screen.findByRole("alert")).textContent).toBe(
      "Our server had a problem. Please try again in a moment."
    );

    await press(user, "Send my answers");

    expect(await screen.findByText("Thank you")).toBeTruthy();
    expect(bodies).toHaveLength(2);
    expect(bodies[1]).toEqual(bodies[0]);
  });

  it("does not send twice when the button is pressed again while the first is on its way", async () => {
    let calls = 0;
    server.use(
      http.put("*/api/v2/coach/plans/:id/checkins/:milestone", async () => {
        calls += 1;
        await new Promise((resolve) => setTimeout(resolve, 100));
        return HttpResponse.json({
          plan_id: PLAN_ID,
          milestone: "d30",
          answers: { remittance: "on_track", savings: "on_track", pay: "full_on_time" },
          answered_at: "2026-12-31T09:12:40Z",
          already_answered: false,
        });
      })
    );
    const user = userEvent.setup();
    renderSheet();
    await choose(user, "Yes, as in my plan");
    await press(user, "Next");
    await choose(user, "Yes, as in my plan");
    await press(user, "Next");
    await choose(user, "Yes, in full and on time");

    await press(user, "Send my answers");
    const sending = screen.getByRole("button", { name: "Sending…" }) as HTMLButtonElement;
    expect(sending.disabled).toBe(true);
    await user.click(sending);

    await screen.findByText("Thank you");
    expect(calls).toBe(1);
  });
});
