import { expect, test } from "@playwright/test";

import { coachApi, type FakeCoach } from "./support/coachApi";
import { conversation, expectAsked } from "./support/coachSteps";
import { signedInWorker } from "./support/emulators";

// What the Coach already knows (NF-FC-015, NF-FC-023, NF-FC-025): a worker whose profile and
// records answer some questions is offered those answers before the first question, keeps or
// changes each one, and is asked only the rest. The offer is docs/mocks/coach/
// sessions-create-03-known.json; a change made here is for this interview only.

let coach: FakeCoach;

test.beforeEach(async ({ page }) => {
  coach = await coachApi(page, { offerKnown: true });
  await signedInWorker(page);
  await page.goto("/coach");
  await expect(page.getByRole("heading", { name: "What we already know" })).toBeVisible();
});

test("the worker keeps most answers, changes one, and is asked only what is left", async ({
  page,
}) => {
  const card = page.getByRole("table", {
    name: "Answers we already know, one row for each question",
  });
  await expect(
    card.getByRole("row", { name: /Country you will work in\s+Singapore/ })
  ).toBeVisible();
  await expect(card.getByRole("row", { name: /Your pay\s+650/ })).toBeVisible();
  // Nothing has been asked yet: the offer comes before the first question.
  expect(coach.turns()).toHaveLength(0);

  await page.getByRole("button", { name: "Change: Kind of work" }).click();
  await expect(card.getByRole("row", { name: /Kind of work\s+I will ask you this/ })).toBeVisible();
  await page.getByRole("button", { name: "Use these answers" }).click();

  // The kept answers are in; the coach asks the first question that is still open.
  await expect(page.getByRole("heading", { name: "What we already know" })).toHaveCount(0);
  await expectAsked(page, "job_type");
  const [applied] = coach.calls.filter((call) => call.path.endsWith("/known"));
  expect(applied.body.keep).toEqual([
    "destination_country",
    "monthly_salary",
    "remittance_target",
    "savings",
    "bank_or_wallet",
  ]);
  expect(Object.keys(coach.session().slots)).toEqual(applied.body.keep);
  // The first question is the coach's own turn; the worker has not been counted as answering.
  expect(coach.session().turn_count).toBe(0);
  await expect(conversation(page).getByText("Hello!")).toBeVisible();
});

test("the worker can ignore the offer and be asked every question", async ({ page }) => {
  await page.getByRole("button", { name: "Ask me every question" }).click();

  await expectAsked(page, "destination_country");
  const [applied] = coach.calls.filter((call) => call.path.endsWith("/known"));
  expect(applied.body.keep).toEqual([]);
  expect(coach.session().slots).toEqual({});
});

test("changing every answer leaves nothing to keep, and says so", async ({ page }) => {
  for (const what of [
    "Country you will work in",
    "Kind of work",
    "Your pay",
    "Money you send home",
    "Your savings",
    "Bank or mobile wallet",
  ]) {
    await page.getByRole("button", { name: `Change: ${what}` }).click();
  }

  await expect(
    page.getByText("You are changing every answer, so I will ask each question.")
  ).toBeVisible();
  await expect(page.getByRole("button", { name: "Use these answers" })).toBeDisabled();
});
