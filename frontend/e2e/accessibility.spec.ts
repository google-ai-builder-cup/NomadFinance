import { readFileSync } from "node:fs";
import path from "node:path";

import { expect, type Page, test } from "@playwright/test";

import { coachApi } from "./support/coachApi";
import { STEPS, answer, expectAsked, panel } from "./support/coachSteps";
import { contractApi, seedCompletedContract } from "./support/contractApi";
import { signedInWorker } from "./support/emulators";
import { fibApi, seedFinancialProfile } from "./support/fibApi";
import { LANGUAGES } from "./support/i18n";
import { mockApi } from "./support/mockApi";

// axe in a real browser, on every signed-in screen, in the light and the dark theme (NF-HR-009).
// The unit tests run axe in jsdom, which has no layout and so cannot judge colour contrast or the
// size of a tap target; this is where those are held. A phone and a desktop run it (the two
// projects), the bar is serious and critical (WCAG 2.0, 2.1 A and AA), and a screen with no data,
// no answer or a failed answer is scanned as well as the one that has everything.

const AXE = readFileSync(path.resolve(process.cwd(), "node_modules/axe-core/axe.min.js"), "utf8");
const PLAN_ID = "5a202702c922fc9b4fcf";
const THEMES = ["light", "dark"] as const;

test.setTimeout(180_000);

test.beforeEach(() => {
  headingless.length = 0;
});

async function inTheme(page: Page, theme: (typeof THEMES)[number]) {
  await page.addInitScript((value) => localStorage.setItem("nomadfinance.theme", value), theme);
}

/** What axe finds wrong on the page now, one readable line per failing element. */
async function violations(page: Page, within?: string): Promise<string[]> {
  await page.evaluate(AXE);
  const found = await page.evaluate(async (scope) => {
    const axe = (window as unknown as { axe: { run: (...args: unknown[]) => Promise<unknown> } })
      .axe;
    const result = (await axe.run(scope ? { include: [[scope]] } : document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"] },
      resultTypes: ["violations"],
    })) as {
      violations: {
        id: string;
        impact: string | null;
        help: string;
        nodes: { target: unknown[]; failureSummary?: string }[];
      }[];
    };
    return result.violations
      .filter((v) => v.impact === "serious" || v.impact === "critical")
      .flatMap((v) => v.nodes.map((n) => `${v.id} [${v.impact}] ${n.target.join(" ")}: ${v.help}`));
  }, within);
  return found;
}

/** Screens that drew no level-1 heading, so a screen reader has no title to start from. */
const headingless: string[] = [];

/** Open `route`, wait for the page to draw, and scan it. */
async function scan(page: Page, route: string, label = route): Promise<string[]> {
  await page.goto(route);
  await settle(page, label);
  return (await violations(page)).map((line) => `${label}: ${line}`);
}

async function settle(page: Page, label: string) {
  await page
    .locator("h1:visible, h2:visible, [role=alert]:visible, [role=status]:visible")
    .first()
    .waitFor({ state: "visible", timeout: 20_000 });
  // The data of the screen arrives and settles, so the whole page is what is checked.
  await page.waitForTimeout(800);
  if ((await page.getByRole("heading", { level: 1 }).count()) === 0) {
    headingless.push(label);
  }
}

function expectClean(found: string[]) {
  expect(found, `axe serious or critical:\n${found.join("\n")}`).toEqual([]);
  expect(headingless, `screens with no level-1 heading:\n${headingless.join("\n")}`).toEqual([]);
}

for (const theme of THEMES) {
  test.describe(`${theme} theme`, () => {
    test("the pages a signed-out visitor sees", async ({ page }) => {
      await inTheme(page, theme);
      const found = [
        ...(await scan(page, "/")),
        ...(await scan(page, "/sign-in")),
        ...(await scan(page, "/no-such-page")),
      ];
      expectClean(found);
    });

    test("the dashboard with the tour, the profile and the scam screens", async ({ page }) => {
      await inTheme(page, theme);
      await mockApi(page);
      await signedInWorker(page);

      const found: string[] = [];
      await page.goto("/dashboard");
      const tour = page.getByRole("dialog", { name: "What is new in NomadFinance" });
      await expect(tour).toBeVisible();
      // With the tour open the page behind it is dimmed and out of reach, so the dialog is what is
      // held to the bar here; the page itself is scanned once the tour is closed.
      found.push(
        ...(await violations(page, "[role=dialog]")).map((line) => `/dashboard (tour): ${line}`)
      );
      await page.keyboard.press("Escape");
      await expect(tour).toBeHidden();
      found.push(...(await scan(page, "/dashboard")));
      found.push(...(await scan(page, "/profile")));
      found.push(...(await scan(page, "/scam-check")));

      // The verdict screen, with the explanation and the warn-others sheet reachable.
      await page
        .getByLabel("The message you received")
        .fill("Pay a 800 SGD fee today or your visa slot is cancelled. Send it to 0000 1234.");
      await page.getByRole("button", { name: "Check this message" }).click();
      await expect(page.getByRole("heading", { name: "This looks like a scam" })).toBeVisible();
      found.push(...(await violations(page)).map((line) => `/scam-check (verdict): ${line}`));

      found.push(...(await scan(page, "/scam-check/history")));
      found.push(...(await scan(page, "/scam-check/history/k_01")));
      expectClean(found);
    });

    test("the Coach: start, an answer, the review, the score, the plan and a check-in", async ({
      page,
    }) => {
      await inTheme(page, theme);
      await coachApi(page);
      await signedInWorker(page);

      const found: string[] = [];
      found.push(...(await scan(page, "/coach", "/coach (first question)")));
      await expectAsked(page, "destination_country");
      await answer(page, "destination_country", STEPS[1].slot);
      found.push(...(await violations(page)).map((line) => `/coach (second question): ${line}`));
      await answer(page, STEPS[1].slot, "review");
      found.push(...(await violations(page)).map((line) => `/coach (review): ${line}`));
      await panel(page).getByRole("button", { name: "Yes, that is right", exact: true }).click();
      await expect(page.getByRole("heading", { name: "Your preparedness score" })).toBeVisible();
      found.push(...(await violations(page)).map((line) => `/coach (score): ${line}`));

      found.push(...(await scan(page, `/coach/plan/${PLAN_ID}`)));
      found.push(...(await scan(page, `/coach/checkin/${PLAN_ID}?m=30`)));
      found.push(...(await scan(page, "/dashboard", "/dashboard (Coach on)")));
      expectClean(found);
    });

    test("Contract Shield and Financial Identity with data", async ({ page }) => {
      await inTheme(page, theme);
      await mockApi(page);
      const user = await signedInWorker(page);
      await contractApi(page, user);
      await fibApi(page, user);
      await seedFinancialProfile(user, "en");
      const contractId = await seedCompletedContract(user);

      const found: string[] = [];
      for (const route of [
        "/contract",
        "/contract/history",
        `/contract/${contractId}`,
        "/identity",
        "/identity/log",
        "/identity/export",
      ]) {
        found.push(...(await scan(page, route)));
      }
      expectClean(found);
    });
  });
}

// The words change the shapes: a Hindi or Tagalog label wraps where an English one does not, and a
// Bengali one needs more height. The home, the profile and the scam check in each of the other
// five languages, with the light theme (the colours do not depend on the language).
for (const language of LANGUAGES.filter((code) => code !== "en")) {
  test(`the home, the profile and the scam check in ${language}`, async ({ page }) => {
    await page.addInitScript((code) => {
      sessionStorage.setItem("nomadfinance.sessionLanguage", code);
    }, language);
    await mockApi(page);
    await signedInWorker(page);

    await page.goto("/dashboard");
    const tour = page.getByRole("dialog");
    await tour.waitFor({ state: "visible", timeout: 5_000 });
    await page.keyboard.press("Escape");
    await expect(tour).toBeHidden();
    const found = [
      ...(await scan(page, "/dashboard", `/dashboard (${language})`)),
      ...(await scan(page, "/profile", `/profile (${language})`)),
      ...(await scan(page, "/scam-check", `/scam-check (${language})`)),
    ];
    expectClean(found);
  });
}

// The keyboard, screen by screen: every control a worker can see takes focus by Tab, and shows
// where the focus is. Pressing Tab walks the page once; a control that was never reached, or that
// shows no outline or ring while it has focus, is listed.
const CONTROLS =
  "a[href], button:not([disabled]), input:not([type=hidden]):not([disabled]), select:not([disabled]), textarea:not([disabled]), [tabindex]:not([tabindex='-1'])";

async function keyboardWalk(page: Page): Promise<{ unreached: string[]; unmarked: string[] }> {
  await page.evaluate((selector) => {
    let n = 0;
    for (const el of Array.from(document.querySelectorAll(selector))) {
      const box = (el as HTMLElement).getBoundingClientRect();
      const style = getComputedStyle(el);
      const shown = box.width > 0 && box.height > 0 && style.visibility !== "hidden";
      // Inside a closed dialog, a hidden menu or an inert region nothing is a tab stop.
      const blocked = el.closest("[inert], [aria-hidden=true]") !== null;
      if (shown && !blocked) {
        el.setAttribute("data-kb", String(n++));
      }
    }
  }, CONTROLS);
  const total = await page.locator("[data-kb]").count();
  await page.evaluate(() => (document.activeElement as HTMLElement | null)?.blur());
  const reached = new Set<string>();
  const unmarked: string[] = [];
  // After a dialog closes the browser carries on from where the dialog was, so the walk is long
  // enough to wrap round the whole page.
  for (let press = 0; press < total * 2 + 8; press++) {
    await page.keyboard.press("Tab");
    const stop = await page.evaluate(() => {
      const el = document.activeElement as HTMLElement | null;
      if (!el || el === document.body) {
        return null;
      }
      const style = getComputedStyle(el);
      const outlined = style.outlineStyle !== "none" && parseFloat(style.outlineWidth) > 0;
      const ringed = style.boxShadow !== "none" && style.boxShadow !== "";
      return {
        id: el.getAttribute("data-kb"),
        name: `${el.tagName.toLowerCase()} "${(el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 40)}"`,
        marked: outlined || ringed,
      };
    });
    if (stop?.id != null) {
      reached.add(stop.id);
      if (!stop.marked) {
        unmarked.push(stop.name);
      }
    }
  }
  const unreached = await page.evaluate(
    (seen) =>
      Array.from(document.querySelectorAll("[data-kb]"))
        .filter((el) => !seen.includes(el.getAttribute("data-kb") ?? ""))
        .map(
          (el) =>
            `${el.tagName.toLowerCase()} "${(el.getAttribute("aria-label") ?? el.textContent ?? "").trim().slice(0, 40)}"`
        ),
    [...reached]
  );
  return { unreached, unmarked: [...new Set(unmarked)] };
}

test("the keyboard reaches every control and shows where it is", async ({ page }) => {
  await mockApi(page);
  await signedInWorker(page);
  const problems: string[] = [];
  for (const route of [
    "/dashboard",
    "/profile",
    "/scam-check",
    "/scam-check/history",
    "/scam-check/history/k_01",
    "/contract",
    "/identity/log",
  ]) {
    await page.goto(route);
    // The first-run tour (a dialog that holds focus) opens once the flags have arrived, and is
    // closed so the page itself is walked.
    if (route === "/dashboard") {
      const tour = page.getByRole("dialog", { name: "What is new in NomadFinance" });
      await tour.waitFor({ state: "visible", timeout: 5_000 });
      await page.keyboard.press("Escape");
      await expect(tour).toBeHidden();
    }
    await settle(page, route);
    const { unreached, unmarked } = await keyboardWalk(page);
    problems.push(...unreached.map((c) => `${route}: not reached by Tab: ${c}`));
    problems.push(...unmarked.map((c) => `${route}: no visible focus: ${c}`));
  }
  expect(problems, problems.join("\n")).toEqual([]);
});

// The screens that ask the API when they open, while the API has not answered (loading) and after
// it failed (error). `/api/v2/flags` answers (both modules on) so these screens are reached; every
// other call hangs or fails with the API's own error shape. A screen that is a form on arrival
// (`/scam-check`, a check-in) asks only when the worker sends, and is scanned above. The screens
// that read Firestore directly (contracts, identity, radar) never see this stub; their states
// are in the unit tests and in docs/runbooks/NF-HR-009-ux-a11y-polish-v2.md.
const API_SCREENS = [
  "/dashboard",
  "/coach",
  `/coach/plan/${PLAN_ID}`,
  "/scam-check/history",
  "/scam-check/history/k_01",
] as const;

// The Contract Shield, Identity, Radar and remittance screens read some of their data from
// Firestore, which this stub does not reach, so they may show their data here. What is held for
// them is the heading in whatever state they are in, and axe.
const V1_SCREENS = [
  "/radar",
  "/radar/heatmap",
  "/radar/alerts",
  "/radar/entity/example-agency",
  "/remittance",
  "/identity",
  "/identity/export",
  "/contract/history",
  "/profile",
] as const;

type Mode = "loading" | "error";

async function withEverythingElse(page: Page, mode: Mode) {
  await page.route("**/api/**", async (route) => {
    const url = new URL(route.request().url());
    if (url.pathname === "/api/v2/flags") {
      return route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({ coach: true, scam: true }),
      });
    }
    if (mode === "loading") {
      return; // never answered: the page is held in its loading state
    }
    return route.fulfill({
      status: 500,
      contentType: "application/json",
      body: JSON.stringify({
        code: "internal_error",
        message: "Something went wrong.",
        request_id: "e2e",
      }),
    });
  });
}

const STATE_MARKER: Record<Mode, string> = {
  // A skeleton, a spinner with a status role, or a region marked busy.
  loading: "[role=status], [aria-busy=true], .animate-pulse",
  // The message of a failed read, announced.
  error: "[role=alert]",
};

for (const theme of THEMES) {
  for (const mode of ["loading", "error"] as const) {
    test(`${theme} theme: the API screens while ${mode === "loading" ? "loading" : "failing"}`, async ({
      page,
    }) => {
      await inTheme(page, theme);
      await withEverythingElse(page, mode);
      await signedInWorker(page);

      const missing: string[] = [];
      const found: string[] = [];
      for (const route of API_SCREENS) {
        await page.goto(route);
        await settle(page, `${route} (${mode})`);
        const marker = page.locator(STATE_MARKER[mode]).first();
        try {
          await marker.waitFor({ state: "visible", timeout: mode === "error" ? 12_000 : 3_000 });
        } catch {
          missing.push(route);
        }
        found.push(...(await violations(page)).map((line) => `${route} (${mode}): ${line}`));
      }
      for (const route of V1_SCREENS) {
        await page.goto(route);
        await settle(page, `${route} (${mode})`);
        found.push(...(await violations(page)).map((line) => `${route} (${mode}): ${line}`));
      }
      expect(missing, `no ${mode} state on:\n${missing.join("\n")}`).toEqual([]);
      expectClean(found);
    });
  }
}
