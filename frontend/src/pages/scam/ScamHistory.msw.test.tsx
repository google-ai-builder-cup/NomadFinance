// @vitest-environment jsdom
// The history screen against the mock API (NF-SA-018): the real page, hook, service and API client
// run, and only the backend's answers come from docs/mocks/scam/.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type JsonBodyType } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { loadNamespace } from "@/lib/i18n";
import { jsonMocks } from "@/mocks/files";
import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";
import ScamHistory from "@/pages/scam/ScamHistory";
import type { ScamCheckList } from "@/types/scam";

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "alice" }, loading: false }) }));
vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("scam");
});

afterEach(cleanup);

const mockBody = (name: string) => jsonMocks.get(name)?.body as ScamCheckList;
const FIRST = mockBody("scam/checks-list-01-first-page.json");
const LAST = mockBody("scam/checks-list-02-last-page.json");

/** Answers each page by its cursor, like the real route, and records every request's address. */
function paged(requests: URL[] = [], pages: Record<string, ScamCheckList> = {}) {
  server.use(
    http.get("*/api/v2/scam/checks", ({ request }) => {
      const url = new URL(request.url);
      requests.push(url);
      const cursor = url.searchParams.get("cursor");
      const body = cursor === null ? FIRST : (pages[cursor] ?? LAST);
      return HttpResponse.json(body as unknown as JsonBodyType);
    })
  );
  return requests;
}

function renderPage() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={["/scam-check/history"]}>
        <Routes>
          <Route path="/scam-check/history" element={<ScamHistory />} />
          <Route path="/scam-check/history/:id" element={<p>detail opened</p>} />
          <Route path="/scam-check" element={<p>check screen</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const rows = () => screen.getAllByRole("listitem");

describe("the history", () => {
  it("lists the checks newest first, each with its risk in words and a way to open it", async () => {
    paged();
    renderPage();

    await screen.findAllByRole("listitem");

    expect(screen.getByRole("heading", { level: 1, name: "Your checks" })).toBeTruthy();
    expect(rows()).toHaveLength(3);
    expect(rows().map((row) => row.querySelector("p")?.textContent)).toEqual([
      "Not a scam",
      "Fake prize or lottery",
      "Loan app trap",
    ]);
    // A scam of medium risk, a scam of low risk and a message that is not a scam: always words.
    expect(within(rows()[0]).getByText("No scam found")).toBeTruthy();
    expect(within(rows()[1]).getByText("Low risk")).toBeTruthy();
    expect(within(rows()[2]).getByText("Medium risk")).toBeTruthy();
    expect(within(rows()[2]).getByText(/Aprubado na ang loan/)).toBeTruthy();
    expect(within(rows()[2]).getByRole("link").getAttribute("href")).toBe(
      "/scam-check/history/k_02"
    );
  });

  it("says how each check was made", async () => {
    paged();
    renderPage();
    await screen.findAllByRole("listitem");

    expect(within(rows()[0]).getByText("Pasted text")).toBeTruthy();
  });

  it("opens a check when its row is tapped", async () => {
    paged();
    renderPage();
    await screen.findAllByRole("listitem");

    await userEvent.click(within(rows()[1]).getByRole("link"));

    expect(await screen.findByText("detail opened")).toBeTruthy();
  });

  it("marks a check the worker already warned others about", async () => {
    const reported: ScamCheckList = {
      ...FIRST,
      items: FIRST.items.map((item) => ({ ...item, reported: item.id === "k_02" })),
    };
    server.use(
      http.get("*/api/v2/scam/checks", () => HttpResponse.json(reported as unknown as JsonBodyType))
    );
    renderPage();
    await screen.findAllByRole("listitem");

    expect(within(rows()[2]).getByText("You warned other workers")).toBeTruthy();
    expect(within(rows()[1]).queryByText("You warned other workers")).toBeNull();
  });
});

describe("paging", () => {
  it("asks for 20 at a time and shows more only when the server has a next page", async () => {
    const requests = paged();
    renderPage();
    await screen.findAllByRole("listitem");

    expect(requests[0].searchParams.get("limit")).toBe("20");
    expect(requests[0].searchParams.has("cursor")).toBe(false);
    expect(screen.getByRole("button", { name: "Show more" })).toBeTruthy();
  });

  it("adds the next page under the first, using the server's cursor, then stops offering more", async () => {
    const requests = paged([], { [FIRST.next_cursor as string]: LAST });
    renderPage();
    await screen.findAllByRole("listitem");

    await userEvent.click(screen.getByRole("button", { name: "Show more" }));

    expect(await screen.findByText("Illegal recruitment fee")).toBeTruthy();
    expect(rows()).toHaveLength(4);
    expect(requests[1].searchParams.get("cursor")).toBe(FIRST.next_cursor);
    expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
  });

  it("keeps what is on screen and says so when the next page cannot be loaded", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v2/scam/checks", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json(FIRST as unknown as JsonBodyType)
          : HttpResponse.json({ code: "internal_error", message: "x" }, { status: 500 });
      })
    );
    renderPage();
    await screen.findAllByRole("listitem");

    await userEvent.click(screen.getByRole("button", { name: "Show more" }));

    expect((await screen.findByRole("alert")).textContent).toMatch(/could not load more checks/);
    expect(rows()).toHaveLength(3);
    expect(screen.getByRole("button", { name: "Show more" })).toBeTruthy();
  });
});

describe("with nothing to show", () => {
  it("shows the empty state, with a way to make the first check", async () => {
    server.use(handlerForMock("scam/checks-list-03-empty.json"));
    renderPage();

    expect(await screen.findByRole("heading", { level: 2, name: "No checks yet" })).toBeTruthy();
    expect(screen.queryByRole("list")).toBeNull();
    expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
    // The page header and the empty state each offer it.
    expect(screen.getAllByRole("link", { name: "Check a message" })).toHaveLength(2);
  });

  it("says so, with a Retry that works, when the history cannot be loaded", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v2/scam/checks", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({ code: "internal_error", message: "x" }, { status: 500 })
          : HttpResponse.json(FIRST as unknown as JsonBodyType);
      })
    );
    renderPage();

    expect((await screen.findByRole("alert")).textContent).toMatch(/could not load your checks/);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(await screen.findByText("Fake prize or lottery")).toBeTruthy();
  });
});

describe("for a keyboard and a screen reader (NF-SA-019)", () => {
  it("moves focus to the first new row after Show more, so it is not lost when the button goes", async () => {
    paged([], { [FIRST.next_cursor as string]: LAST });
    renderPage();
    await screen.findAllByRole("listitem");

    await userEvent.click(screen.getByRole("button", { name: "Show more" }));

    await screen.findByText("Illegal recruitment fee");
    expect(screen.queryByRole("button", { name: "Show more" })).toBeNull();
    expect(document.activeElement).toBe(within(rows()[3]).getByRole("link"));
  });

  it("keeps the retry button at 44 px", async () => {
    server.use(
      http.get("*/api/v2/scam/checks", () =>
        HttpResponse.json({ code: "internal_error", message: "x" }, { status: 500 })
      )
    );
    renderPage();

    const retry = await screen.findByRole("button", { name: "Try again" });

    expect(retry.className).toContain("min-h-11");
  });
});
