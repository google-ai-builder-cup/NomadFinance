import { expect, test } from "@playwright/test";

import { signedInWorker } from "./support/emulators";
import { type MockApi, mockApi, mockBody } from "./support/mockApi";

// The history (NF-SA-020): the worker's earlier checks, a page at a time, each one opening the
// stored answer. The list and the detail come from docs/mocks/scam/.

interface HistoryPage {
  items: { id: string; excerpt: string }[];
  next_cursor: string | null;
}

let api: MockApi;

test.beforeEach(async ({ page }) => {
  api = await mockApi(page);
  await signedInWorker(page);
});

test("the history lists checks, loads the next page and opens a stored check", async ({ page }) => {
  const first = mockBody<HistoryPage>("scam/checks-list-01-first-page.json");
  const second = mockBody<HistoryPage>("scam/checks-list-02-last-page.json");

  await page.goto("/scam-check");
  await page.getByRole("link", { name: "Your checks" }).first().click();

  await expect(page).toHaveURL(/\/scam-check\/history$/);
  await expect(page.getByRole("heading", { level: 1, name: "Your checks" })).toBeVisible();
  for (const item of first.items) {
    await expect(page.getByText(item.excerpt, { exact: false })).toBeVisible();
  }

  await page.getByRole("button", { name: "Show more" }).click();
  for (const item of second.items) {
    await expect(page.getByText(item.excerpt, { exact: false })).toBeVisible();
  }
  expect(
    api
      .to("GET", /\/scam\/checks$/)
      .at(-1)
      ?.query.get("cursor")
  ).toBe(first.next_cursor);
  await expect(page.getByRole("button", { name: "Show more" })).toHaveCount(0);

  await page.getByText(first.items[0].excerpt, { exact: false }).click();
  await expect(page).toHaveURL(new RegExp(`/scam-check/history/${first.items[0].id}$`));
  await expect(page.getByRole("heading", { name: /Check from/ })).toBeVisible();
  await expect(page.getByRole("heading", { name: "This does not look like a scam" })).toBeVisible();

  await page.getByRole("link", { name: "Back to your checks" }).click();
  await expect(page).toHaveURL(/\/scam-check\/history$/);
});

test("a worker with no checks sees an empty list and a way to make the first one", async ({
  page,
}) => {
  api.answerHistoryWith("scam/checks-list-03-empty.json");

  await page.goto("/scam-check/history");

  await expect(page.getByRole("heading", { name: "No checks yet" })).toBeVisible();
  await expect(page.getByRole("link", { name: "Check a message" }).first()).toBeVisible();
});

test("a check that has expired says so instead of showing an error", async ({ page }) => {
  await page.goto("/scam-check/history/k_gone");

  await expect(page.getByRole("heading", { name: "We could not find this check" })).toBeVisible();
});
