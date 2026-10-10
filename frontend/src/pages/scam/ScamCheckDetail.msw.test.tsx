// @vitest-environment jsdom
// One stored check against the mock API (NF-SA-018): the real page, hook, service and API client
// run, and only the backend's answers come from docs/mocks/scam/.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type JsonBodyType } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { loadNamespace } from "@/lib/i18n";
import { jsonMocks } from "@/mocks/files";
import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";
import ScamCheckDetail from "@/pages/scam/ScamCheckDetail";

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "alice" }, loading: false }) }));
vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("scam");
});

afterEach(cleanup);

function renderPage(id = "k_01") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[`/scam-check/history/${id}`]}>
        <Routes>
          <Route path="/scam-check/history/:id" element={<ScamCheckDetail />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("a stored check", () => {
  it("is drawn like a fresh result, with the day it was checked and the day it is removed", async () => {
    renderPage();

    expect(
      await screen.findByRole("heading", { level: 2, name: "This looks like a scam" })
    ).toBeTruthy();

    const title = screen.getByRole("heading", { level: 1 }).textContent ?? "";
    expect(title).toMatch(/^Check from .*2026/);
    expect(screen.getByText(/Saved until .*2027, then removed\./)).toBeTruthy();
    expect(screen.getByRole("heading", { name: "Why this is a scam" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "What to do now" })).toBeTruthy();
  });

  it("offers to warn other workers, and the way back to the list and on to a new check", async () => {
    renderPage();
    await screen.findByRole("heading", { level: 2, name: "This looks like a scam" });

    expect(screen.getByRole("button", { name: "Warn other workers" })).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to your checks" }).getAttribute("href")).toBe(
      "/scam-check/history"
    );
    expect(screen.getByRole("link", { name: "Check another message" }).getAttribute("href")).toBe(
      "/scam-check"
    );
    // A stored check is a page of its own: no button that resets a form.
    expect(screen.queryByRole("button", { name: "Check another message" })).toBeNull();
  });

  it("shows the button already done for a check the worker reported", async () => {
    const mock = jsonMocks.get("scam/check-01-high-risk.json")?.body as Record<string, unknown>;
    server.use(
      http.get("*/api/v2/scam/checks/k_01", () =>
        HttpResponse.json({ ...mock, reported: true, report_id: "r_02" } as JsonBodyType)
      )
    );
    renderPage();

    const done = await screen.findByRole("button", { name: "You warned other workers" });

    expect((done as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByRole("link", { name: "See it in Radar" }).getAttribute("href")).toBe(
      "/radar/entity/scam-illegal-recruitment-fee"
    );
  });

  it("offers no warning for a message that was not a scam", async () => {
    server.use(handlerForMock("scam/check-04-benign.json"));
    renderPage("k_04");

    expect(
      await screen.findByRole("heading", { level: 2, name: "This does not look like a scam" })
    ).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Warn other workers" })).toBeNull();
  });
});

describe("the page's heading", () => {
  it("is there while the check loads, when it is gone and when the read fails", async () => {
    server.use(http.get("*/api/v2/scam/checks/k_slow", () => new Promise<never>(() => undefined)));
    const loading = renderPage("k_slow");
    expect(screen.getByRole("heading", { level: 1, name: "Your checks" })).toBeTruthy();
    expect(screen.getByRole("status")).toBeTruthy();
    loading.unmount();

    server.use(handlerForMock("scam/check-error-not-found.json"));
    const gone = renderPage("k_missing");
    await screen.findByRole("heading", { level: 2, name: "We could not find this check" });
    expect(screen.getByRole("heading", { level: 1, name: "Your checks" })).toBeTruthy();
    gone.unmount();

    server.use(
      http.get("*/api/v2/scam/checks/k_broken", () =>
        HttpResponse.json({ code: "internal_error", message: "x" }, { status: 500 })
      )
    );
    renderPage("k_broken");
    await screen.findByRole("alert");
    expect(screen.getByRole("heading", { level: 1, name: "Your checks" })).toBeTruthy();
  });
});

describe("a check that cannot be shown", () => {
  it("says it is gone, in the same words for missing, expired and someone else's", async () => {
    server.use(handlerForMock("scam/check-error-not-found.json"));
    renderPage("k_missing");

    expect(
      await screen.findByRole("heading", { level: 2, name: "We could not find this check" })
    ).toBeTruthy();
    expect(screen.getByText(/older than 90 days/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Back to your checks" })).toBeTruthy();
  });

  it("says it could not be loaded after a server error, with a Try again that works", async () => {
    let calls = 0;
    const mock = jsonMocks.get("scam/check-01-high-risk.json")?.body as JsonBodyType;
    server.use(
      http.get("*/api/v2/scam/checks/k_01", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({ code: "internal_error", message: "x" }, { status: 500 })
          : HttpResponse.json(mock);
      })
    );
    renderPage();

    expect((await screen.findByRole("alert")).textContent).toMatch(/could not load this check/);
    await userEvent.click(screen.getByRole("button", { name: "Try again" }));

    expect(
      await screen.findByRole("heading", { level: 2, name: "This looks like a scam" })
    ).toBeTruthy();
  });
});
