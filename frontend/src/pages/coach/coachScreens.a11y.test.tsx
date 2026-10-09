// @vitest-environment jsdom
// Accessibility and translation of the Coach's screens (NF-FC-023): the interview in each of its
// states, the plan and the check-in, in all six languages, checked with axe and for any string
// that would show as a raw key. The parts the score and the plan are made of have their own
// checks beside them; colour contrast and tap-target size need a real browser, see
// docs/runbooks/NF-FC-023-coach-i18n-a11y.md.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { memoryBackend, setOutboxBackend } from "@/lib/coachOutboxStore";
import i18n, { loadNamespace, setLanguage } from "@/lib/i18n";
import { axeViolations, rawKeysShown } from "@/mocks/axe";
import { replaySession, replayTurns, sessionFrom } from "@/mocks/coachTurns";
import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";
import CoachCheckinPage from "@/pages/coach/CoachCheckinPage";
import CoachHome from "@/pages/coach/CoachHome";
import CoachPlanPage from "@/pages/coach/CoachPlanPage";
import { LANGUAGE_CODES } from "@/types/enums";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { uid: "worker-1" }, loading: false }),
}));
vi.mock("@/services/notificationService", () => ({ markNotificationRead: async () => undefined }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
beforeEach(() => {
  setOutboxBackend(memoryBackend());
  localStorage.clear();
});
afterEach(async () => {
  cleanup();
  setOutboxBackend(null);
  await act(() => setLanguage("en"));
});

const inLanguage = (code: string) => act(() => setLanguage(code));

function withApp(entry: string, routes: React.ReactNode) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        {/* The app shell supplies the page's landmark; a screen alone has none. */}
        <main>
          <Routes>{routes}</Routes>
        </main>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const renderCoach = () => withApp("/coach", <Route path="/coach" element={<CoachHome />} />);

/** The interview opens with this session instead of the new one the mock API gives by default. */
function startWith(name: string, changes: Record<string, unknown> = {}) {
  server.use(
    http.post("*/api/v2/coach/sessions", () =>
      HttpResponse.json({ ...sessionFrom(name), resumed: false, ...changes })
    )
  );
}

async function expectFit(container: HTMLElement) {
  expect(await axeViolations(container)).toEqual([]);
  expect(rawKeysShown(container)).toEqual([]);
}

describe.each(LANGUAGE_CODES)("in %s", (language) => {
  it("the interview, at its first question", async () => {
    await inLanguage(language);
    replayTurns("coach/turn-01-start.sse");
    const { container } = renderCoach();
    // The stream of the mock is the same in every language: only the screen around it changes.
    await within(await screen.findByRole("log")).findByText(/Which country are you going to work/);

    await expectFit(container);
  });

  it("the interview, in the middle, with the money helper open", async () => {
    await inLanguage(language);
    startWith("coach/session-02-debt.json");
    replayTurns("coach/turn-01-start.sse");
    const { container } = renderCoach();
    await screen.findByRole("log");

    await expectFit(container);
  });

  it("the welcome-back banner", async () => {
    await inLanguage(language);
    startWith("coach/session-02-debt.json", { resumed: true });
    const { container } = renderCoach();
    await screen.findByRole("log");
    // The banner is the region that holds the choice to carry on or to start over.
    expect(screen.getAllByRole("region")).toHaveLength(1);

    await expectFit(container);
  });

  it("the card of what the Coach already knows", async () => {
    await inLanguage(language);
    startWith("coach/sessions-create-03-known.json");
    const { container } = renderCoach();
    await screen.findByRole("table");

    await expectFit(container);
  });

  it("the card, with a row changed", async () => {
    await inLanguage(language);
    startWith("coach/sessions-create-03-known.json");
    const user = userEvent.setup();
    const { container } = renderCoach();
    const table = await screen.findByRole("table");
    await user.click(within(table).getAllByRole("button")[2] as HTMLElement);

    await expectFit(container);
  });

  it("the review, with its table of answers", async () => {
    await inLanguage(language);
    startWith("coach/session-03-review.json");
    const { container } = renderCoach();
    await screen.findByRole("table");

    await expectFit(container);
  });

  it("the question before a new interview", async () => {
    await inLanguage(language);
    startWith("coach/session-02-debt.json");
    const user = userEvent.setup();
    const { container } = renderCoach();
    await screen.findByRole("log");
    const nav = screen.getByRole("navigation");
    await user.click(within(nav).getByRole("button"));

    await expectFit(container);
  });

  it("the finished screen: score, plan button and the whole conversation", async () => {
    await inLanguage(language);
    startWith("coach/session-04-plan-mid.json");
    replaySession();
    const { container } = renderCoach();
    await screen.findByRole("img", { name: /57/ });

    // Every score carries the "not financial advice" note, in the worker's language (D-229).
    const note = i18n.t("score.disclaimer", { lng: language, ns: "coach" });
    expect(note).not.toBe("score.disclaimer");
    expect(screen.getByText(note)).toBeTruthy();
    await expectFit(container);
  });

  it("the plan", async () => {
    await inLanguage(language);
    server.use(handlerForMock("coach/plan-get-01-english.json"));
    const { container } = withApp(
      "/coach/plan/5a202702c922fc9b4fcf",
      <Route path="/coach/plan/:planId" element={<CoachPlanPage />} />
    );
    await screen.findByRole("heading", { level: 1 });

    await expectFit(container);
  });

  it("the check-in", async () => {
    await inLanguage(language);
    const { container } = withApp(
      "/coach/checkin/5a202702c922fc9b4fcf?m=30",
      <Route path="/coach/checkin/:planId" element={<CoachCheckinPage />} />
    );
    await screen.findByRole("heading", { level: 1 });

    await expectFit(container);
  });
});
