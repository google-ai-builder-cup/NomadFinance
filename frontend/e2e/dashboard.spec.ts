import { expect, test } from "@playwright/test";

import { contractApi, seedCompletedContract } from "./support/contractApi";
import { signedInWorker, type TestUser } from "./support/emulators";
import { fibApi, seedFinancialProfile } from "./support/fibApi";
import { LANGUAGES } from "./support/i18n";
import { mockApi, readMock } from "./support/mockApi";

// The home dashboard with both new modules on (NF-HR-002): it stays within two screens on a 360 px
// phone, and the first-run tour is shown once and can be skipped. The scam module is on for the
// worker (docs/mocks/flags/flags-scam-on.json); the Coach is not, so the tour has two steps.

// Phones first: the page is compact only below 640 px, so this is the size that is being held.
test.use({ viewport: { width: 360, height: 740 } });

let worker: TestUser;

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  worker = await signedInWorker(page);
});

test("the tour is shown once, walks through the new module and is not shown again", async ({
  page,
}) => {
  await page.goto("/dashboard");

  const tour = page.getByRole("dialog", { name: "What is new in NomadFinance" });
  await expect(tour).toBeVisible();
  await expect(tour.getByText("Step 1 of 2")).toBeVisible();
  await expect(tour.getByRole("heading", { name: "Check a message before you act" })).toBeVisible();

  await tour.getByRole("button", { name: "Next" }).click();
  await expect(tour.getByRole("heading", { name: "All in one place" })).toBeVisible();
  await tour.getByRole("button", { name: "Got it" }).click();
  await expect(tour).toBeHidden();

  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("the tour can be skipped, and Escape counts as skipping", async ({ page }) => {
  await page.goto("/dashboard");
  const tour = page.getByRole("dialog", { name: "What is new in NomadFinance" });
  await expect(tour).toBeVisible();

  await page.keyboard.press("Escape");

  await expect(tour).toBeHidden();
  await page.reload();
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();
  await expect(page.getByRole("dialog")).toHaveCount(0);
});

test("the page is at most two screens tall and does not scroll sideways", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("dialog").getByRole("button", { name: "Skip" }).click();
  // The cards load on their own; wait until the Scam Check card has its status.
  await expect(page.getByText(/Last check:/)).toBeVisible();

  const size = await page.evaluate(() => ({
    height: document.documentElement.scrollHeight,
    viewport: window.innerHeight,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
  }));

  expect(size.height).toBeLessThanOrEqual(size.viewport * 2);
  expect(size.overflow).toBeLessThanOrEqual(0);
});

test("the Scam Check card opens Scam Check", async ({ page }) => {
  await page.goto("/dashboard");
  await page.getByRole("dialog").getByRole("button", { name: "Skip" }).click();

  await page.getByRole("link", { name: "Check a message" }).last().click();

  await expect(page).toHaveURL(/\/scam-check$/);
});

// The same limit in each of the six languages, with the fullest home a worker has: both modules on,
// a contract, an identity score, a scam check, an interview under way and a plan (NF-HR-009). A
// language whose sentences wrap more has less room, so the English check above is not enough.
for (const language of LANGUAGES) {
  test(`the page is at most two screens tall in ${language}`, async ({ page }) => {
    await page.addInitScript((code) => {
      sessionStorage.setItem("nomadfinance.sessionLanguage", code);
    }, language);
    // The web font comes from Google Fonts. Measured with it, the page is as tall as the network
    // lets the font be; measured without, it is the page of a worker whose font has not arrived,
    // which is the tallest it gets and the same on every run. That is the one held to the limit.
    await page.route(/fonts\.(googleapis|gstatic)\.com/, (route) => route.abort());
    await contractApi(page, worker);
    await fibApi(page, worker);
    await seedFinancialProfile(worker, language);
    await seedCompletedContract(worker);
    // Later routes answer first: both modules on, and the Coach card with a session and a plan.
    const answer = (name: string) => {
      const mock = readMock(name);
      return {
        status: mock.status,
        contentType: "application/json",
        body: JSON.stringify(mock.body),
      };
    };
    await page.route("**/api/v2/flags", (route) =>
      route.fulfill({
        status: 200,
        contentType: "application/json",
        body: '{"coach":true,"scam":true}',
      })
    );
    await page.route("**/api/v2/coach/overview", (route) =>
      route.fulfill(answer("coach/overview-03-session-and-plan.json"))
    );

    // Both cards that change the height have their answers before it is measured (the promises
    // are made before the page is opened, so an answer that is quick is not missed).
    const answered = Promise.all([
      page.waitForResponse((response) => response.url().includes("/api/v2/coach/overview")),
      page.waitForResponse((response) => response.url().includes("/api/v2/scam/checks")),
    ]);
    await page.goto("/dashboard");
    await page.getByRole("dialog").getByRole("button").last().click();
    await answered;
    await page.evaluate(() => document.fonts.ready);
    await page.waitForTimeout(800);

    const size = await page.evaluate(() => ({
      height: document.documentElement.scrollHeight,
      viewport: window.innerHeight,
      overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    }));
    console.log(`dashboard ${language}: ${size.height} px of ${size.viewport * 2}`);

    expect(size.height).toBeLessThanOrEqual(size.viewport * 2);
    expect(size.overflow).toBeLessThanOrEqual(0);
  });
}
