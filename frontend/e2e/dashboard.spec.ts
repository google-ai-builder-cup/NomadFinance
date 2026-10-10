import { expect, test } from "@playwright/test";

import { signedInWorker } from "./support/emulators";
import { mockApi } from "./support/mockApi";

// The home dashboard with both new modules on (NF-HR-002): it stays within two screens on a 360 px
// phone, and the first-run tour is shown once and can be skipped. The scam module is on for the
// worker (docs/mocks/flags/flags-scam-on.json); the Coach is not, so the tour has two steps.

// Phones first: the page is compact only below 640 px, so this is the size that is being held.
test.use({ viewport: { width: 360, height: 740 } });

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  await signedInWorker(page);
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
