// @vitest-environment jsdom
// The Coach page against the mock API (NF-FC-017): it starts or resumes the worker's interview,
// opens it with the coach's first question, and starts a new one when asked.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { replayOverview, replayTurns, sessionFrom } from "@/mocks/coachTurns";
import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";
import { loadNamespace } from "@/lib/i18n";
import { memoryBackend, setOutboxBackend } from "@/lib/coachOutboxStore";
import CoachHome from "@/pages/coach/CoachHome";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));
// The page keeps drafts and a waiting answer under the signed-in person (NF-FC-019).
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { uid: "worker-1" }, loading: false }),
}));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
beforeEach(() => {
  setOutboxBackend(memoryBackend());
  localStorage.clear();
});
afterEach(() => {
  cleanup();
  setOutboxBackend(null);
});

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/coach"]}>
        <CoachHome />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

// The log appears once the session has loaded.
const inLog = async (text: RegExp) => within(await screen.findByRole("log")).findByText(text);

describe("starting", () => {
  it("shows a loading state, then the first question of a new interview", async () => {
    const sent = replayTurns("coach/turn-01-start.sse");

    renderPage();

    expect(screen.getByRole("status", { name: "Opening the coach…" })).toBeTruthy();
    expect(screen.getByRole("heading", { level: 1, name: "Financial Coach" })).toBeTruthy();
    await inLog(/Which country are you going to work in\?/);
    expect(screen.queryByRole("status", { name: "Opening the coach…" })).toBeNull();
    expect(sent).toHaveLength(1);
    expect(sent[0].body).toEqual({ language: "en" });
  });

  it("starts the session in the language of the app", async () => {
    let body: unknown;
    server.use(
      http.post("*/api/v2/coach/sessions", async ({ request }) => {
        body = await request.json();
        return HttpResponse.json(sessionFrom("coach/sessions-create-01-new.json"), { status: 201 });
      })
    );
    replayTurns("coach/turn-01-start.sse");

    renderPage();
    await inLog(/Which country/);

    expect(body).toEqual({ language: "en" });
  });

  it("resumes an open interview with its transcript and no new opening turn", async () => {
    server.use(handlerForMock("coach/sessions-create-02-resumed.json"));
    const sent = replayTurns("coach/turn-02-answer.sse");

    renderPage();

    await inLog(/नमस्ते! मैं आपका पैसों का साथी हूँ।/);
    expect(sent).toHaveLength(0);
    expect(screen.getByText("Step 4 of 6: Debt")).toBeTruthy();
  });

  it("welcomes a worker back to an interview that is under way, and says where it stopped", async () => {
    server.use(handlerForMock("coach/sessions-create-02-resumed.json"));
    replayTurns("coach/turn-02-answer.sse");

    renderPage();

    const banner = await screen.findByRole("region", { name: "Welcome back" });
    expect(banner.textContent).toContain("Step 4 of 6: Debt");
    expect(banner.textContent).toContain("Your answers are saved.");
  });

  it("does not welcome a worker back to an interview that has just begun", async () => {
    replayTurns("coach/turn-01-start.sse");

    renderPage();

    await inLog(/Which country are you going to work in\?/);
    expect(screen.queryByRole("region", { name: "Welcome back" })).toBeNull();
  });

  it("says the coach could not be opened, and tries again", async () => {
    let calls = 0;
    server.use(
      http.post("*/api/v2/coach/sessions", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json(
              { code: "ai_unavailable", message: "x", request_id: "r" },
              { status: 503 }
            )
          : HttpResponse.json(sessionFrom("coach/sessions-create-01-new.json"), { status: 201 });
      })
    );
    replayTurns("coach/turn-01-start.sse");
    const user = userEvent.setup();
    renderPage();

    const notice = (await screen.findByText(/The coach is busy right now/)).closest(
      "[role='alert']"
    );
    await user.click(within(notice as HTMLElement).getByRole("button", { name: "Try again" }));

    await inLog(/Which country are you going to work in\?/);
    expect(calls).toBe(2);
  });
});

describe("starting over", () => {
  it("closes a finished interview and opens a new one with the coach's first question", async () => {
    const bodies: unknown[] = [];
    server.use(
      http.post("*/api/v2/coach/sessions", async ({ request }) => {
        const body = (await request.json()) as { restart?: boolean };
        bodies.push(body);
        return HttpResponse.json(
          body.restart
            ? sessionFrom("coach/sessions-create-01-new.json", { id: "s_09" })
            : sessionFrom("coach/session-02-debt.json", { resumed: true }),
          { status: body.restart ? 201 : 200 }
        );
      })
    );
    const sent = replayTurns({ refusal: "coach/turn-error-session-not-active.json" });
    const user = userEvent.setup();
    renderPage();
    await user.click(await screen.findByRole("button", { name: "None (0)" }));
    const notice = (await screen.findByText(/This interview is finished/)).closest(
      "[role='alert']"
    );
    // The next turns belong to the new interview.
    sent.length = 0;
    replayTurns("coach/turn-01-start.sse");

    await user.click(
      within(notice as HTMLElement).getByRole("button", { name: "Start a new interview" })
    );

    await inLog(/Which country are you going to work in\?/);
    expect(bodies).toEqual([{ language: "en" }, { language: "en", restart: true }]);
    await waitFor(() => expect(screen.queryByText(/This interview is finished/)).toBeNull());
    // The old interview's lines are gone: a new chat, not the old one with a new line.
    expect(screen.getByRole("log").textContent).not.toContain("नमस्ते");
  });
});

describe("the way back to a plan", () => {
  it("offers the plan the worker made, above the interview", async () => {
    replayTurns("coach/turn-01-start.sse");
    replayOverview("coach/overview-02-plan-only.json");

    renderPage();

    const link = await screen.findByRole("link", { name: "View my plan" });
    expect(link.getAttribute("href")).toBe("/coach/plan/5a202702c922fc9b4fcf");
    expect(screen.getByText("Your 90-day plan is ready")).toBeTruthy();
    await inLog(/Which country are you going to work in\?/);
  });

  it("offers nothing when no plan was made", async () => {
    replayTurns("coach/turn-01-start.sse");
    replayOverview("coach/overview-04-empty.json");

    renderPage();

    await inLog(/Which country are you going to work in\?/);
    expect(screen.queryByRole("link", { name: "View my plan" })).toBeNull();
  });

  it("leaves the page as it was when the overview cannot be read", async () => {
    replayTurns("coach/turn-01-start.sse");
    server.use(
      http.get("*/api/v2/coach/overview", () =>
        HttpResponse.json({ code: "internal", message: "x" }, { status: 500 })
      )
    );

    renderPage();

    await inLog(/Which country are you going to work in\?/);
    expect(screen.queryByRole("link", { name: "View my plan" })).toBeNull();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});
