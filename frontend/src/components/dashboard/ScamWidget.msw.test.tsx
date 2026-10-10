// @vitest-environment jsdom
// The Scam Check card on the home dashboard (NF-HR-002): what the last check found, or an invitation
// to make the first one, and never a missing way in.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import ScamWidget from "@/components/dashboard/ScamWidget";
import { MODULE_ITEMS } from "@/components/layout/navItems";
import { setLanguage } from "@/lib/i18n";
import { axeViolations, rawKeysShown } from "@/mocks/axe";
import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";
import { LANGUAGE_CODES } from "@/types/enums";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

const ITEM = MODULE_ITEMS.find((item) => item.flag === "scam");
const DAY = 86_400_000;

beforeAll(async () => {
  await setLanguage("en");
});
afterEach(async () => {
  cleanup();
  await act(async () => void (await setLanguage("en")));
});

function renderCard() {
  if (ITEM === undefined) {
    throw new Error("The Scam Check module item is missing");
  }
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <ScamWidget item={ITEM} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

function newestCheck(overrides: Record<string, unknown>) {
  server.use(
    http.get("*/api/v2/scam/checks", () =>
      HttpResponse.json({
        items: [
          {
            id: "k_01",
            created_at: new Date(Date.now() - 2 * DAY).toISOString(),
            input_type: "text",
            language: "en",
            is_scam: true,
            scam_type: "illegal_recruitment_fee",
            risk_level: "high",
            confidence: 0.9,
            excerpt: "Pay the fee",
            reported: false,
            ...overrides,
          },
        ],
        next_cursor: null,
      })
    )
  );
}

describe("the card's status", () => {
  it("asks only for the newest check", async () => {
    let asked = "";
    server.use(
      http.get("*/api/v2/scam/checks", ({ request }) => {
        asked = new URL(request.url).searchParams.get("limit") ?? "";
        return HttpResponse.json({ items: [], next_cursor: null });
      })
    );

    renderCard();
    await screen.findByText("Paste a message to check it before you act.");

    expect(asked).toBe("1");
  });

  it("invites a first check when there is no history", async () => {
    server.use(handlerForMock("scam/checks-list-03-empty.json"));

    renderCard();

    expect(await screen.findByText("Paste a message to check it before you act.")).toBeTruthy();
  });

  it("says what the last check found and how long ago", async () => {
    newestCheck({ risk_level: "high" });

    renderCard();

    expect(await screen.findByText("Last check: high risk, 2 days ago.")).toBeTruthy();
  });

  it("says no scam was found for a message that was not one", async () => {
    newestCheck({ is_scam: false, risk_level: "low" });

    renderCard();

    expect(await screen.findByText("Last check: no scam found, 2 days ago.")).toBeTruthy();
  });

  it("leaves the time out when it is not usable", async () => {
    newestCheck({ created_at: "not a date" });

    renderCard();

    expect(await screen.findByText("Last check: high risk.")).toBeTruthy();
  });

  it("is the plain pitch with its link while the history loads", () => {
    server.use(http.get("*/api/v2/scam/checks", () => new Promise(() => undefined)));

    renderCard();

    expect(screen.getByText(/Paste a message or a screenshot/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "Check a message" })).toBeTruthy();
  });

  it("keeps the way in when the history cannot be read", async () => {
    server.use(
      http.get("*/api/v2/scam/checks", () =>
        HttpResponse.json({ code: "internal", message: "x" }, { status: 500 })
      )
    );

    renderCard();

    expect(await screen.findByRole("link", { name: "Check a message" })).toBeTruthy();
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("the card's link", () => {
  it("opens Scam Check, whatever the status", async () => {
    newestCheck({});

    renderCard();
    await screen.findByText(/Last check/);

    expect(screen.getByRole("link", { name: "Check a message" }).getAttribute("href")).toBe(
      "/scam-check"
    );
  });
});

describe("in the six languages", () => {
  it.each(LANGUAGE_CODES)("shows no raw key in %s and passes axe", async (code) => {
    newestCheck({});
    await act(async () => void (await setLanguage(code)));

    const view = renderCard();
    await screen.findByRole("link");
    await act(async () => undefined);

    expect(rawKeysShown(view.container)).toEqual([]);
    expect(await axeViolations(view.container)).toEqual([]);
  });
});
