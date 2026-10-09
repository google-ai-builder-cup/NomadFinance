// @vitest-environment jsdom
// The 90-day plan screen against the recorded plans of docs/mocks/coach/ (NF-FC-021): its sections,
// the warnings most serious first, the figures as the PDF writes them, the link into Remittance
// X-Ray, the checklist kept on the phone, a plan that is missing, and the app's six languages.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import CoachPlanPage from "@/pages/coach/CoachPlanPage";
import i18n, { loadNamespace, setLanguage } from "@/lib/i18n";
import { axeViolations, rawKeysShown } from "@/mocks/axe";
import { jsonMocks } from "@/mocks/files";
import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";
import { LANGUAGE_CODES } from "@/types/enums";
import { CHECKLIST_KEY_PREFIX } from "@/utils/coachStorageKeys";

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "alice" }, loading: false }) }));
vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
beforeEach(() => localStorage.clear());
afterEach(async () => {
  cleanup();
  await act(async () => void (await setLanguage("en")));
});

const ENGLISH = "coach/plan-get-01-english.json";
const HINDI = "coach/plan-get-02-hindi.json";
const NO_DEBT = "coach/plan-get-03-no-debt.json";
const NOT_FOUND = "coach/plan-get-error-not-found.json";
const ID = "5a202702c922fc9b4fcf";
const NO_DEBT_ID = "e75fa9f24fd3159ad83d";

function renderPlan(planId = ID) {
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter initialEntries={[`/coach/plan/${planId}`]}>
        <Routes>
          <Route path="/coach/plan/:planId" element={<CoachPlanPage />} />
          <Route path="/coach" element={<p>The Coach page</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const section = async (name: string) =>
  (await screen.findByRole("heading", { name })).closest("section") as HTMLElement;

describe("a plan with a provider and a debt", () => {
  beforeEach(() => server.use(handlerForMock(ENGLISH)));

  it("shows every section, in the order the worker needs them", async () => {
    renderPlan();

    await screen.findByRole("heading", { level: 1, name: "Your 90-day plan" });
    const headings = screen
      .getAllByRole("heading", { level: 2 })
      .map((heading) => heading.textContent);

    expect(headings).toEqual([
      "Look at these first",
      "Your month",
      "Sending money home",
      "Your debt",
      "Emergency savings",
      "Week by week",
      "Before you leave",
      "Take it with you",
    ]);
  });

  it("states the score and the route", async () => {
    renderPlan();

    await screen.findByRole("heading", { level: 1 });

    expect(screen.getByText(/Score \d+ · /)).toBeTruthy();
    expect(screen.getByText("AU → IN")).toBeTruthy();
  });

  it("puts the urgent warning first and writes its severity as a word", async () => {
    renderPlan();

    const panel = await screen.findByRole("heading", { name: "Look at these first" });
    const items = within(panel.closest("section") as HTMLElement).getAllByRole("listitem");

    expect(items.map((item) => item.querySelector("p")?.textContent)).toEqual([
      "Urgent",
      "Warning",
      "Note",
    ]);
  });

  it("writes the figures as the PDF does, with a currency code and plain digits", async () => {
    renderPlan();

    const month = await section("Your month");
    await within(month).findByText("4,200 AUD");

    expect(within(month).getByText("245 AUD")).toBeTruthy();
    expect(within(month).getByText("600 AUD")).toBeTruthy();
    expect(within(month).getByText("Housing")).toBeTruthy();
    expect(within(month).getByText("1,100 AUD")).toBeTruthy();
    expect(within(month).queryByText("Short each month by")).toBeNull();
  });

  it("links to Remittance X-Ray with the corridor and the monthly amount", async () => {
    renderPlan();

    const link = await screen.findByRole("link", { name: "Compare in Remittance X-Ray" });

    expect(link.getAttribute("href")).toBe("/remittance?corridor=AU-IN&amount=900");
  });

  it("lists the weeks to send money and marks them in the timeline", async () => {
    renderPlan();

    const remittance = await section("Sending money home");
    await within(remittance).findByText("Week 5 · 900 AUD");
    expect(within(remittance).getByText("Week 9 · 900 AUD")).toBeTruthy();
    expect(within(remittance).getByText("Week 13 · 900 AUD")).toBeTruthy();

    const timeline = (await section("Week by week")).querySelector("ol") as HTMLElement;
    const weeks = Array.from(timeline.children) as HTMLElement[];
    expect(weeks).toHaveLength(13);
    const marked = weeks
      .filter((week) => within(week).queryByText("Send money") !== null)
      .map((week) => week.textContent);
    expect(marked).toHaveLength(3);
  });

  it("shows the debt and the emergency savings", async () => {
    renderPlan();

    await screen.findByRole("heading", { name: "Your debt" });

    expect(within(await section("Emergency savings")).getByText("6,465 AUD")).toBeTruthy();
    expect(within(await section("Emergency savings")).getByText("66 weeks")).toBeTruthy();
  });

  it("ends with the disclaimer, the PDF and the way back", async () => {
    renderPlan();

    await screen.findByRole("heading", { name: "Take it with you" });

    expect(screen.getByRole("button", { name: "Download PDF" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to the Coach" }).getAttribute("href")).toBe(
      "/coach"
    );
  });
});

describe("a plan with no debt and no provider quote", () => {
  beforeEach(() => server.use(handlerForMock(NO_DEBT)));

  it("leaves out the debt card and the comparison link, and says why", async () => {
    renderPlan(NO_DEBT_ID);

    await screen.findByRole("heading", { level: 1 });

    expect(screen.queryByRole("heading", { name: "Your debt" })).toBeNull();
    expect(screen.queryByRole("link", { name: "Compare in Remittance X-Ray" })).toBeNull();
    expect(
      within(await section("Sending money home")).getByText(/cannot compare prices/)
    ).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Emergency savings" })).toBeTruthy();
  });

  it("shows amounts in a currency without decimals, grouped", async () => {
    renderPlan(NO_DEBT_ID);

    expect(await within(await section("Your month")).findByText("2,400,000 KRW")).toBeTruthy();
  });
});

describe("the checklist", () => {
  beforeEach(() => server.use(handlerForMock(ENGLISH)));

  it("starts unticked and counts what is done", async () => {
    renderPlan();

    const boxes = await screen.findAllByRole("checkbox");

    expect(boxes).toHaveLength(5);
    expect(boxes.every((box) => !(box as HTMLInputElement).checked)).toBe(true);
    expect(screen.getByText("0 of 5 done")).toBeTruthy();
  });

  it("keeps a tick on the phone, by id, and shows it again on the next visit", async () => {
    const user = userEvent.setup();
    const first = renderPlan();
    await user.click((await screen.findAllByRole("checkbox"))[0]);

    expect(screen.getByText("1 of 5 done")).toBeTruthy();
    expect(localStorage.getItem(`${CHECKLIST_KEY_PREFIX}alice.${ID}`)).toBe('["keep_documents"]');
    first.unmount();

    renderPlan();
    await screen.findByRole("heading", { name: "Before you leave" });

    expect((screen.getAllByRole("checkbox")[0] as HTMLInputElement).checked).toBe(true);
    expect(screen.getByText("1 of 5 done")).toBeTruthy();
  });

  it("takes a tick back", async () => {
    const user = userEvent.setup();
    renderPlan();
    const box = (await screen.findAllByRole("checkbox"))[1];

    await user.click(box);
    await user.click(box);

    expect(screen.getByText("0 of 5 done")).toBeTruthy();
    expect(localStorage.getItem(`${CHECKLIST_KEY_PREFIX}alice.${ID}`)).toBeNull();
  });
});

describe("a plan that cannot be opened", () => {
  it("says it was not found, with no retry, and offers the way back", async () => {
    server.use(handlerForMock(NOT_FOUND, "GET /api/v2/coach/plans/0123456789abcdef0123"));

    renderPlan("0123456789abcdef0123");

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("We could not find this plan")).toBeTruthy();
    expect(within(alert).queryByRole("button", { name: "Try again" })).toBeNull();
    expect(within(alert).getByRole("link", { name: "Back to the Coach" })).toBeTruthy();
  });

  it("offers a retry on a server error, and shows the plan when it works", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v2/coach/plans/:id", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({ code: "bad_gateway", message: "x" }, { status: 502 })
          : HttpResponse.json(planBody());
      })
    );
    const user = userEvent.setup();
    renderPlan();

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByText("We could not open your plan")).toBeTruthy();
    await user.click(within(alert).getByRole("button", { name: "Try again" }));

    expect(await screen.findByRole("heading", { level: 1, name: "Your 90-day plan" })).toBeTruthy();
  });
});

describe("the language", () => {
  it("asks for the plan in the app's language", async () => {
    const asked: (string | null)[] = [];
    server.use(
      http.get("*/api/v2/coach/plans/:id", ({ request }) => {
        asked.push(new URL(request.url).searchParams.get("language"));
        return HttpResponse.json(planBody());
      })
    );

    renderPlan();
    await screen.findByRole("heading", { level: 1 });

    expect(asked).toEqual(["en"]);
  });

  it("keeps the plan on screen with a note while the other language is translated", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => (release = resolve));
    server.use(
      http.get("*/api/v2/coach/plans/:id", async ({ request }) => {
        if (new URL(request.url).searchParams.get("language") === "hi") {
          await gate;
          return HttpResponse.json(hindiBody());
        }
        return HttpResponse.json(planBody());
      })
    );
    renderPlan();
    await screen.findByRole("heading", { name: "Before you leave" });

    await act(async () => void (await setLanguage("hi")));

    const banner = i18n.getFixedT("hi", "coach")("plan.translating");
    expect(await screen.findByText(banner)).toBeTruthy();
    expect(
      screen.getByText("Keep copies of your contract, passport and agent receipts.", {
        exact: false,
      })
    ).toBeTruthy();
    release();

    const first = (hindiBody().plan as { checklist: { text: string }[] }).checklist[0].text;
    expect(await screen.findByText(first)).toBeTruthy();
    expect(screen.queryByText(banner)).toBeNull();
    expect(screen.queryByText(/Keep copies of your contract/)).toBeNull();
    expect(document.querySelector("[lang='hi']")).not.toBeNull();
  });
});

describe("what a worker can use", () => {
  beforeEach(() => server.use(handlerForMock(ENGLISH)));

  it("has no accessibility violation on the page", async () => {
    const view = renderPlan();
    await screen.findByRole("heading", { name: "Before you leave" });

    expect(await axeViolations(view.container)).toEqual([]);
  });

  it("shows no untranslated key, in any of the six languages", async () => {
    for (const code of LANGUAGE_CODES) {
      server.use(http.get("*/api/v2/coach/plans/:id", () => HttpResponse.json(planBody())));
      await act(async () => void (await setLanguage(code)));
      const view = renderPlan();
      await screen.findByRole("heading", { level: 1 });

      expect(rawKeysShown(view.container), code).toEqual([]);
      view.unmount();
    }
  });
});

function mockBody(name: string): Record<string, unknown> {
  const body = jsonMocks.get(name)?.body;
  if (body === undefined) {
    throw new Error(`No mock "${name}" in docs/mocks/.`);
  }
  return body as Record<string, unknown>;
}

const planBody = () => mockBody(ENGLISH);
const hindiBody = () => mockBody(HINDI);
