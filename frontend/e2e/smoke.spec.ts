import { expect, test } from "@playwright/test";

// The sample end-to-end test (NF-F0-014): a worker opens the app, reads the landing page and
// reaches the sign-in page. It needs no backend and no account, so it runs the same everywhere.
// The text below is the English copy in src/i18n/en.json; a copy change means changing it here.

test("the landing page loads and its call to action leads to sign-in", async ({ page }) => {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(error.message));

  await page.goto("/");

  await expect(page).toHaveTitle(/NomadFinance/);
  await expect(
    page.getByRole("heading", { level: 1, name: /Your pay\. Your contract\./ })
  ).toBeVisible();

  await page.getByRole("link", { name: "Get started" }).first().click();

  await expect(page).toHaveURL(/\/sign-in$/);
  await expect(page.getByRole("heading", { name: "Sign in to NomadFinance" })).toBeVisible();
  expect(problems, "uncaught errors in the page").toEqual([]);
});

test("the landing page does not scroll sideways at this screen size", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  );

  expect(overflow).toBeLessThanOrEqual(0);
});

test("a page that does not exist is handled by the app, not the server", async ({ page }) => {
  const response = await page.goto("/no-such-page");

  // Hosting sends every path to index.html, so the status is 200 and the app shows its own page.
  expect(response?.status()).toBe(200);
  await expect(page.locator("#root")).not.toBeEmpty();
});
