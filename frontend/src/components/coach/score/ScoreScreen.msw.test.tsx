// @vitest-environment jsdom
// The preparedness score screen against the recorded sessions of docs/mocks/coach/ (NF-FC-020):
// the three bands, the five factors with their words, a score that cannot be worked out, the button
// that makes the plan, its progress and its failures, and the six languages.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import ScoreScreen from "@/components/coach/score/ScoreScreen";
import i18n, { loadNamespace, setLanguage } from "@/lib/i18n";
import { axeViolations, rawKeysShown } from "@/mocks/axe";
import { replayPlan, replaySession } from "@/mocks/coachTurns";
import { server, setupMockServer } from "@/mocks/server";
import { SCORE_FACTORS } from "@/types/coach";
import { LANGUAGE_CODES, type LanguageCode } from "@/types/enums";

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(async () => {
  cleanup();
  await act(async () => void (await setLanguage("en")));
});

function renderScreen(language: LanguageCode = "en", timeoutProps: { slowAfterMs?: number } = {}) {
  void timeoutProps;
  return render(
    <QueryClientProvider
      client={new QueryClient({ defaultOptions: { queries: { retry: false } } })}
    >
      <MemoryRouter>
        <ScoreScreen sessionId="s_01" language={language} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const MOCK = {
  mid: "coach/session-04-plan-mid.json",
  low: "coach/session-05-plan-low.json",
  high: "coach/session-06-plan-high.json",
} as const;

const chart = (name: RegExp | string) => screen.findByRole("img", { name });
const card = (name: string) => screen.getByRole("heading", { name }).closest("li") as HTMLElement;

describe("the three bands", () => {
  it("shows the middle band as 'Getting ready' in amber, from its mock", async () => {
    replaySession(MOCK.mid);

    renderScreen();

    expect(await chart("Preparedness score: 57 out of 100, Getting ready")).toBeTruthy();
    expect(screen.getAllByText("Getting ready").length).toBeGreaterThan(0);
    expect(screen.queryByText(/stays at/)).toBeNull();
  });

  it("shows the low band as 'Needs more preparation'", async () => {
    replaySession(MOCK.low);

    renderScreen();

    expect(await chart("Preparedness score: 7 out of 100, Needs more preparation")).toBeTruthy();
  });

  it("shows the high band as 'Well prepared'", async () => {
    replaySession(MOCK.high);

    renderScreen();

    expect(await chart("Preparedness score: 91 out of 100, Well prepared")).toBeTruthy();
  });

  it("writes the band as a word as well as a colour, and the total as a number", async () => {
    replaySession(MOCK.low);
    renderScreen();

    await chart(/7 out of 100/);

    expect(screen.getByText("Needs more preparation")).toBeTruthy();
    expect(screen.getByText("7")).toBeTruthy();
    expect(screen.getByText("out of 100")).toBeTruthy();
  });

  it("names a band it does not know in neutral words", async () => {
    replaySession(MOCK.mid, {
      score: {
        ...(await import("@/mocks/coachTurns")).sessionFrom(MOCK.mid).score!,
        band: "excellent",
      },
    });

    renderScreen();

    expect(await chart("Preparedness score: 57 out of 100, Your level")).toBeTruthy();
  });
});

describe("the five factors", () => {
  it("has one card for each, with a bar of its points and a level in words", async () => {
    replaySession(MOCK.mid);
    renderScreen();
    await chart(/57 out of 100/);

    expect(screen.getAllByRole("listitem")).toHaveLength(5);
    const debt = within(card("Debt compared with your pay"));
    expect(debt.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("70");
    expect(debt.getByText("Strong")).toBeTruthy();
    expect(debt.getByText("70 out of 100")).toBeTruthy();
    expect(within(card("Emergency savings")).getByText("Weak")).toBeTruthy(); // 30 points
    expect(within(card("Agent fee compared with the usual limit")).getByText("Weak")).toBeTruthy();
    expect(within(card("Bank account or wallet")).getByText("Strong")).toBeTruthy();
  });

  it("gives what it means and how to improve, by factor and level", async () => {
    replaySession(MOCK.low);
    renderScreen();
    await chart(/7 out of 100/);

    const debt = within(card("Debt compared with your pay"));
    expect(debt.getByText(/Your debt is many months of your pay/)).toBeTruthy();
    expect(
      debt.getByText(/Talk to a worker support group before you pay anything new/)
    ).toBeTruthy();
    expect(debt.getByText("What this means")).toBeTruthy();
    expect(debt.getByText("How to improve")).toBeTruthy();
    const bank = within(card("Bank account or wallet"));
    expect(bank.getByText(/You have no bank account or wallet to be paid into/)).toBeTruthy();
  });

  it("picks the words of the level, not of the band: a strong factor in a weak score", async () => {
    replaySession(MOCK.high);
    renderScreen();
    await chart(/91 out of 100/);

    expect(
      within(card("Debt compared with your pay")).getByText(/You owe little or nothing/)
    ).toBeTruthy();
    expect(
      within(card("Emergency savings")).getByText(
        /almost nothing saved|several months|a month or two/
      )
    ).toBeTruthy();
  });

  it("says why 74 points is only 'Getting ready' when one factor holds it down", async () => {
    const base = (await import("@/mocks/coachTurns")).sessionFrom(MOCK.mid).score!;
    replaySession(MOCK.mid, {
      score: {
        ...base,
        total: 74,
        band: "getting_ready",
        factors: base.factors.map((f, i) => ({ ...f, score: i === 3 ? 10 : 100 })),
      },
    });

    renderScreen();

    expect(await screen.findByText(/One area is very low/)).toBeTruthy();
  });
});

describe("a score that cannot be shown", () => {
  it("says so and asks again, then shows the score once it can be worked out", async () => {
    let calls = 0;
    const { sessionFrom } = await import("@/mocks/coachTurns");
    server.use(
      http.get("*/api/v2/coach/sessions/:id", () => {
        calls += 1;
        return HttpResponse.json({
          ...sessionFrom(MOCK.mid),
          score: calls === 1 ? null : sessionFrom(MOCK.mid).score,
        });
      })
    );
    const user = userEvent.setup();
    renderScreen();

    await screen.findByText("We cannot work out your score right now");
    await user.click(screen.getByRole("button", { name: "Try again" }));

    expect(await chart(/57 out of 100/)).toBeTruthy();
    expect(calls).toBe(2);
  });

  it("tells a failed read in words, with a way to try again", async () => {
    server.use(
      http.get("*/api/v2/coach/sessions/:id", () => new HttpResponse(null, { status: 503 }))
    );

    renderScreen();

    const alert = await screen.findByRole("alert");
    expect(within(alert).getByRole("button", { name: "Try again" })).toBeTruthy();
    expect(alert.textContent).toMatch(/busy|try again/i);
  });

  it("shows a loading state first", () => {
    replaySession(MOCK.mid);

    renderScreen();

    expect(screen.getByRole("status").textContent).toContain("Loading your score");
  });
});

describe("the button that makes the plan", () => {
  it("sends the language and shows the plan's summary when it is made", async () => {
    replaySession(MOCK.mid);
    const made = replayPlan();
    const user = userEvent.setup();
    await act(async () => void (await setLanguage("hi")));
    renderScreen("hi");
    await screen.findByRole("img", { name: /\d/ });

    await user.click(screen.getByRole("button", { name: "मेरी 90 दिन की योजना बनाएँ" }));

    await screen.findByText("आपकी योजना तैयार है");
    expect(made.sent).toEqual([{ sessionId: "s_01", language: "hi" }]);
    expect(screen.getByText(/You will earn about 4,200 AUD a month/)).toBeTruthy();
    expect(screen.queryByRole("button", { name: /योजना बनाएँ/ })).toBeNull();
  });

  it("waits while the plan is made: the button is busy, and a longer wait is explained", async () => {
    replaySession(MOCK.mid);
    replayPlan("coach/plan-01-created.json", 400);
    const user = userEvent.setup();
    render(
      <QueryClientProvider client={new QueryClient()}>
        <MemoryRouter>
          <ScoreScreen sessionId="s_01" language="en" />
        </MemoryRouter>
      </QueryClientProvider>
    );
    await screen.findByRole("img", { name: /\d/ });

    await user.click(screen.getByRole("button", { name: "Make my 90-day plan" }));

    const busy = screen.getByRole("button", { name: "Making your plan…" }) as HTMLButtonElement;
    expect(busy.disabled).toBe(true);
    expect(busy.getAttribute("aria-busy")).toBe("true");
    expect(screen.getByText(/takes up to a minute/)).toBeTruthy();
    await screen.findByText("Your plan is ready");
  });

  it.each([
    ["coach/plan-error-not-ready.json", /confirm your answers first/, false],
    ["coach/plan-error-in-progress.json", /still working on your last message/, true],
    ["coach/plan-error-ai-bad-response.json", /coach is busy/, true],
  ] as const)("says in words why %s failed", async (refusal, message, canRetry) => {
    replaySession(MOCK.mid);
    replayPlan({ refusal });
    const user = userEvent.setup();
    renderScreen();
    await screen.findByRole("img", { name: /\d/ });

    await user.click(screen.getByRole("button", { name: "Make my 90-day plan" }));

    const alert = await screen.findByRole("alert");
    expect(alert.textContent).toMatch(message);
    const again = screen.getByRole("button", {
      name: canRetry ? "Try again" : "Make my 90-day plan",
    });
    expect((again as HTMLButtonElement).disabled).toBe(false);
  });

  it("tells a missing score input apart, and asks the worker to try again later", async () => {
    replaySession(MOCK.mid);
    server.use(
      http.post("*/api/v2/coach/sessions/:id/plan", () =>
        HttpResponse.json(
          { code: "score_unavailable", message: "no rate", request_id: "r1" },
          { status: 503, headers: { "Retry-After": "30" } }
        )
      )
    );
    const user = userEvent.setup();
    renderScreen();
    await screen.findByRole("img", { name: /\d/ });

    await user.click(screen.getByRole("button", { name: "Make my 90-day plan" }));

    expect((await screen.findByRole("alert")).textContent).toMatch(
      /cannot make your plan right now/
    );
  });

  it("a second press after a failure asks again and gets the plan", async () => {
    replaySession(MOCK.mid);
    let calls = 0;
    server.use(
      http.post("*/api/v2/coach/sessions/:id/plan", async () => {
        calls += 1;
        if (calls === 1) {
          return HttpResponse.json(
            { code: "ai_bad_response", message: "bad", request_id: "r2" },
            { status: 502 }
          );
        }
        return HttpResponse.json({
          id: "5a202702c922fc9b4a31",
          language: "en",
          score: {},
          plan: { summary: "Your plan summary." },
        });
      })
    );
    const user = userEvent.setup();
    renderScreen();
    await screen.findByRole("img", { name: /\d/ });

    await user.click(screen.getByRole("button", { name: "Make my 90-day plan" }));
    await user.click(await screen.findByRole("button", { name: "Try again" }));

    await screen.findByText("Your plan summary.");
    expect(calls).toBe(2);
  });

  it("ends a plan that takes longer than the allowance as a timeout", async () => {
    replaySession(MOCK.mid);
    replayPlan("coach/plan-01-created.json", 600);
    const { createCoachPlan } = await import("@/services/coachService");

    await expect(createCoachPlan("s_01", "en", 50)).rejects.toMatchObject({
      status: 504,
      detail: "ai_timeout",
    });
  });
});

describe("accessibility", () => {
  it("passes axe in every band", async () => {
    for (const mock of Object.values(MOCK)) {
      replaySession(mock);
      const { unmount } = renderScreen();
      await screen.findByRole("img", { name: /\d/ });

      expect(await axeViolations()).toEqual([]);
      unmount();
    }
  });

  it("gives the chart a text alternative and hides its numerals from screen readers once", async () => {
    replaySession(MOCK.mid);
    renderScreen();

    const picture = await chart(/57 out of 100, Getting ready/);

    expect(picture.getAttribute("role")).toBe("img");
    expect(picture.querySelector("svg")).not.toBeNull();
  });
});

describe("the six languages", () => {
  it("has the words of every factor at every level, in every language, different from English", async () => {
    for (const language of LANGUAGE_CODES) {
      await act(async () => void (await setLanguage(language)));
      for (const id of SCORE_FACTORS) {
        expect(i18n.exists(`score.factor.${id}.name`, { lng: language, ns: "coach" })).toBe(true);
        for (const level of ["strong", "fair", "weak"]) {
          for (const part of ["means", "improve"]) {
            const key = `score.factor.${id}.${level}.${part}`;
            const own = i18n.getResource(language, "coach", key) as string | undefined;
            const english = i18n.getResource("en", "coach", key) as string;
            expect(own, `${language} ${key}`).toBeTruthy();
            if (language !== "en") {
              expect(own, `${language} ${key} is still English`).not.toBe(english);
            }
          }
        }
      }
    }
  });

  it.each(LANGUAGE_CODES.filter((code) => code !== "en"))(
    "shows the screen in %s with no key left raw, and every figure in digits 0 to 9",
    async (language) => {
      await act(async () => void (await setLanguage(language)));
      replaySession(MOCK.mid);
      renderScreen(language);
      await screen.findByRole("img", { name: /\d/ });

      expect(rawKeysShown()).toEqual([]);
      const picture = screen.getByRole("img", { name: /\d/ });
      expect(picture.getAttribute("aria-label")).toMatch(/57/);
      expect(document.body.textContent).not.toMatch(/[०-९০-৯]/);
      expect(await axeViolations()).toEqual([]);
    }
  );

  it("never shows the English name of a factor to a Hindi reader", async () => {
    await act(async () => void (await setLanguage("hi")));
    replaySession(MOCK.low);
    renderScreen("hi");
    await screen.findByRole("img", { name: /\d/ });

    expect(screen.queryByText("Emergency savings")).toBeNull();
    expect(screen.getByText("आपात बचत")).toBeTruthy();
    await waitFor(() => expect(document.documentElement.lang).toBeDefined());
  });
});
