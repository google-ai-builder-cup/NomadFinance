import { expect, test } from "@playwright/test";

import { coachApi, type FakeCoach } from "./support/coachApi";
import { STEPS, answer, conversation, expectAsked, panel } from "./support/coachSteps";
import { signedInWorker } from "./support/emulators";

// Coming back to an interview under way (NF-FC-019, NF-FC-025): the worker closes the tab or the
// page reloads half way through, and finds the same step, the same conversation and what they had
// typed. The server stand-in keeps the interview, as the real one does.

let coach: FakeCoach;

test.beforeEach(async ({ page }) => {
  coach = await coachApi(page);
  await signedInWorker(page);
  await page.goto("/coach");
  await expectAsked(page, "destination_country");
  // Six answers in: the coach is asking what the worker paid the agent (step 4 of 6, Debt).
  await answer(page, "destination_country", "recruitment_fee_paid");
});

test("after a reload the worker is welcomed back at the same step, with what they had typed", async ({
  page,
}) => {
  await panel(page).getByLabel("Amount", { exact: true }).fill("150");

  await page.reload();

  const banner = page.getByRole("region", { name: "Welcome back" });
  await expect(banner).toBeVisible();
  await expect(banner).toContainText("Step 4 of 6: Debt");
  await expect(banner).toContainText("Your answers are saved.");
  // The conversation is back, the question is the same, and so is the unsent amount.
  await expectAsked(page, "recruitment_fee_paid");
  await expect(conversation(page).getByText(STEPS[0].sent).first()).toBeVisible();
  await expect(panel(page).getByLabel("Amount", { exact: true })).toHaveValue("150");

  // The interview was kept by the server: nothing was asked or answered again.
  expect(coach.turns().filter((turn) => turn.body.text === undefined)).toHaveLength(1);
  expect(coach.session().turn_count).toBe(6);

  // Carrying on from there reaches the review.
  await banner.getByRole("button", { name: "Continue" }).click();
  await expect(banner).toHaveCount(0);
  await panel(page).getByLabel("Amount", { exact: true }).fill("150000");
  await panel(page).getByLabel("Currency").selectOption("INR");
  await panel(page).getByRole("button", { name: "Send", exact: true }).click();
  await expectAsked(page, "debt_outstanding");
  await answer(page, "debt_outstanding", "review");
  expect(coach.session().stage).toBe("review");
});

test("starting over asks first, and then begins a new interview", async ({ page }) => {
  await page.reload();
  const banner = page.getByRole("region", { name: "Welcome back" });
  await expect(banner).toBeVisible();

  await banner.getByRole("button", { name: "Start a new interview" }).click();
  await expect(banner).toContainText("Starting a new interview closes this one and its answers.");
  await banner.getByRole("button", { name: "No, keep going" }).click();
  await expect(banner.getByRole("button", { name: "Continue" })).toBeVisible();
  expect(coach.calls.filter((call) => call.body.restart)).toHaveLength(0);

  await banner.getByRole("button", { name: "Start a new interview" }).click();
  await banner.getByRole("button", { name: "Yes, start over" }).click();

  await expectAsked(page, "destination_country");
  await expect(page.getByRole("region", { name: "Welcome back" })).toHaveCount(0);
  expect(coach.calls.filter((call) => call.body.restart)).toHaveLength(1);
  expect(coach.session().turn_count).toBe(0);
  expect(coach.session().id).toBe("s_e2e_2");
});
