// @vitest-environment jsdom
// `/coach/checkin/:planId?m=30` (NF-FC-022): the page a reminder's link opens.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { loadNamespace } from "@/lib/i18n";
import { setupMockServer } from "@/mocks/server";
import CoachCheckinPage from "@/pages/coach/CoachCheckinPage";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));
vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { uid: "worker-1" }, loading: false }),
}));
vi.mock("@/services/notificationService", () => ({ markNotificationRead: async () => undefined }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(cleanup);

function renderAt(address: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[address]}>
        <Routes>
          <Route path="/coach/checkin/:planId" element={<CoachCheckinPage />} />
          <Route path="/coach" element={<p>The Coach</p>} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

describe("the check-in page", () => {
  it.each([
    ["30", "Day 30 check-in"],
    ["60", "Day 60 check-in"],
    ["90", "Day 90 check-in"],
  ])("opens the day %s check-in from the reminder's link", (days, title) => {
    renderAt(`/coach/checkin/5a202702c922fc9b4fcf?m=${days}`);

    expect(screen.getByRole("heading", { level: 1, name: title })).toBeTruthy();
    expect(screen.getByText("Question 1 of 3")).toBeTruthy();
    expect(
      screen.getByRole("group", { name: "Did you send money home as in your plan?" })
    ).toBeTruthy();
  });

  it.each(["", "?m=45", "?m=abc", "?m="])(
    "does not ask the questions for a link with %j, and leads to the Coach instead",
    (query) => {
      renderAt(`/coach/checkin/5a202702c922fc9b4fcf${query}`);

      expect(
        screen.getByRole("heading", { level: 1, name: "This check-in link is not complete" })
      ).toBeTruthy();
      expect(screen.queryByRole("group")).toBeNull();
      expect(screen.getByRole("link", { name: "Open the Coach" }).getAttribute("href")).toBe(
        "/coach"
      );
    }
  );
});
