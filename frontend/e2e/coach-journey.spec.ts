import { expect, test } from "@playwright/test";

import { coachApi, type FakeCoach } from "./support/coachApi";
import { STEPS, answer, expectAsked, panel } from "./support/coachSteps";
import { signedInWorker } from "./support/emulators";
import { mockBody } from "./support/mockApi";

// The whole Coach journey in a real browser (NF-FC-025): start, answer every question with the
// screen's own helpers, confirm the review, read the score, make the plan, read it and save the
// PDF. The Coach's routes are a stand-in that holds the interview in memory (support/coachApi.ts);
// the plan and the score are the mock files of docs/mocks/coach/. The English copy is in
// src/i18n/coach/en.json.

let coach: FakeCoach;

test.beforeEach(async ({ page }) => {
  coach = await coachApi(page);
  await signedInWorker(page);
});

test("from the first question to the saved PDF", async ({ page }) => {
  const problems: string[] = [];
  page.on("pageerror", (error) => problems.push(error.message));
  const plan = mockBody<{ id: string; plan: { summary: string } }>(
    "coach/plan-get-01-english.json"
  );

  await page.goto("/coach");
  await expect(page.getByRole("heading", { level: 1, name: "Financial Coach" })).toBeVisible();
  await expectAsked(page, "destination_country");

  // Every question, answered through the helper made for it.
  await answer(page, "destination_country", "review");
  expect(coach.turns().map((turn) => turn.body.text)).toEqual([
    undefined, // the coach speaks first
    ...STEPS.map((step) => step.sent),
  ]);
  expect(new Set(coach.turns().map((turn) => turn.key)).size).toBe(coach.turns().length);

  // The review: every answer in a table, then yes.
  const review = page.getByRole("table", { name: "Your answers, one row for each question" });
  await expect(
    review.getByRole("row", { name: /Country you will work in\s+Australia/ })
  ).toBeVisible();
  await expect(review.getByRole("row", { name: /Your pay\s+4,?200/ })).toBeVisible();
  await panel(page).getByRole("button", { name: "Yes, that is right", exact: true }).click();

  // The score, worked out by the server, comes before the plan.
  await expect(page.getByRole("heading", { name: "All your answers are in" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your preparedness score" })).toBeVisible();
  await expect(page.getByText("Getting ready").first()).toBeVisible();
  await expect(page.getByText("57").first()).toBeVisible();

  await page.getByRole("button", { name: "Make my 90-day plan" }).click();
  await expect(page.getByText("Your plan is ready")).toBeVisible();
  await page.getByRole("link", { name: "View my plan" }).click();

  await expect(page).toHaveURL(new RegExp(`/coach/plan/${plan.id}$`));
  await expect(page.getByRole("heading", { level: 1, name: "Your 90-day plan" })).toBeVisible();
  await expect(page.getByText(plan.plan.summary)).toBeVisible();

  const download = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download PDF" }).click();
  const file = await download;
  expect(file.suggestedFilename()).toBe("nomadfinance-plan-en.pdf");
  const bytes = await (await import("node:fs/promises")).readFile(await file.path());
  expect(bytes.subarray(0, 5).toString("latin1")).toBe("%PDF-");

  expect(problems, "uncaught errors in the page").toEqual([]);
});

test("an answer can be typed instead of picked", async ({ page }) => {
  await page.goto("/coach");
  await expectAsked(page, "destination_country");

  await page.getByRole("button", { name: "Type my own answer" }).click();
  await page.getByRole("textbox", { name: "Your answer" }).fill("I will work in Australia");
  await page.getByRole("button", { name: "Send", exact: true }).click();

  await expectAsked(page, "job_type");
  expect(coach.turns().at(-1)?.body).toEqual({ text: "I will work in Australia", language: "en" });
  // The next question brings its own helper back.
  await expect(page.getByRole("button", { name: "Care worker", exact: true })).toBeVisible();
});

test("the screens of the journey do not scroll sideways", async ({ page }) => {
  const overflow = () =>
    page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
  await page.goto("/coach");
  await expectAsked(page, "destination_country");
  expect(await overflow(), "the first question").toBeLessThanOrEqual(0);

  await answer(page, "destination_country", "review");
  expect(await overflow(), "the review").toBeLessThanOrEqual(0);

  await panel(page).getByRole("button", { name: "Yes, that is right", exact: true }).click();
  await expect(page.getByRole("heading", { name: "Your preparedness score" })).toBeVisible();
  expect(await overflow(), "the score").toBeLessThanOrEqual(0);

  await page.getByRole("button", { name: "Make my 90-day plan" }).click();
  await page.getByRole("link", { name: "View my plan" }).click();
  await expect(page.getByRole("heading", { level: 1, name: "Your 90-day plan" })).toBeVisible();
  expect(await overflow(), "the plan").toBeLessThanOrEqual(0);
});

test("once the plan is made, the Coach page leads back to it", async ({ page }) => {
  await page.goto("/coach");
  await expectAsked(page, "destination_country");
  await answer(page, "destination_country", "review");
  await panel(page).getByRole("button", { name: "Yes, that is right", exact: true }).click();
  await page.getByRole("button", { name: "Make my 90-day plan" }).click();
  await expect(page.getByText("Your plan is ready")).toBeVisible();

  await page.goto("/coach");

  await expect(page.getByText("Your 90-day plan is ready")).toBeVisible();
  await page.getByRole("link", { name: "View my plan" }).first().click();
  await expect(page.getByRole("heading", { level: 1, name: "Your 90-day plan" })).toBeVisible();
});
