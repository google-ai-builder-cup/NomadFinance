import { expect, test } from "@playwright/test";

import { coachApi, coachText, type FakeCoach } from "./support/coachApi";
import { answer, conversation, expectAsked, panel } from "./support/coachSteps";
import { signedInWorker } from "./support/emulators";

// An answer sent with no signal (NF-FC-019, NF-FC-025): it is kept on the phone, shown as waiting,
// and delivered once, with the same key, when the connection is back. The test cuts the network
// twice over: the browser is put offline (so the app sees `navigator.onLine` change, as on a
// phone in flight mode) and the stand-in server refuses every call.
//
// Not covered: the service worker that sends a waiting answer with the app closed (Chrome on
// Android). The tests run with service workers blocked, because the app's own would answer
// before the test's routes can (playwright.config.ts).

let coach: FakeCoach;

const FEE = "150000 INR";

async function sendFee(page: import("@playwright/test").Page) {
  await panel(page).getByLabel("Amount", { exact: true }).fill("150000");
  await panel(page).getByLabel("Currency").selectOption("INR");
  await panel(page).getByRole("button", { name: "Send", exact: true }).click();
}

const feeTurns = () => coach.turns().filter((turn) => turn.body.text === FEE);

test.beforeEach(async ({ page }) => {
  coach = await coachApi(page);
  await signedInWorker(page);
  await page.goto("/coach");
  await expectAsked(page, "destination_country");
  await answer(page, "destination_country", "recruitment_fee_paid");
});

test("an answer sent with no signal waits, and is delivered once when the signal is back", async ({
  page,
  context,
}) => {
  coach.setOffline(true);
  await context.setOffline(true);

  await sendFee(page);

  // Kept and shown as waiting, not as a failure; the panel is locked until it is delivered.
  const talk = conversation(page);
  await expect(talk.getByText(FEE)).toBeVisible();
  await expect(talk.getByText(coachText("en", "offline.waiting"))).toBeVisible();
  await expect(
    page.getByRole("status").filter({ hasText: coachText("en", "offline.notice") })
  ).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
  await expect(panel(page).getByRole("button", { name: "Send", exact: true })).toBeDisabled();
  expect(feeTurns()).toHaveLength(0);

  coach.setOffline(false);
  await context.setOffline(false);

  await expectAsked(page, "debt_outstanding");
  await expect(talk.getByText(coachText("en", "offline.waiting"))).toHaveCount(0);
  await expect(
    page.getByRole("status").filter({ hasText: coachText("en", "offline.notice") })
  ).toHaveCount(0);
  // Exactly once: one turn with this answer reached the server, which counted it once.
  expect(feeTurns()).toHaveLength(1);
  expect(coach.session().turn_count).toBe(7);
  expect(coach.session().messages.filter((message) => message.text === FEE)).toHaveLength(1);
});

test("a waiting answer comes back after a reload and goes with Send now", async ({
  page,
  context,
}) => {
  coach.setOffline("turns");
  await context.setOffline(true);
  await sendFee(page);
  await expect(conversation(page).getByText(coachText("en", "offline.waiting"))).toBeVisible();

  // The phone has a signal again, but the answer still cannot get through; the page is reloaded.
  await context.setOffline(false);
  await page.reload();
  await expect(conversation(page).getByText(FEE)).toBeVisible();
  await expect(conversation(page).getByText(coachText("en", "offline.waiting"))).toBeVisible();
  expect(feeTurns()).toHaveLength(0);

  coach.setOffline(false);
  await page.getByRole("button", { name: coachText("en", "offline.sendNow") }).click();

  await expectAsked(page, "debt_outstanding");
  await expect(conversation(page).getByText(coachText("en", "offline.waiting"))).toHaveCount(0);
  expect(feeTurns()).toHaveLength(1);
  expect(coach.session().turn_count).toBe(7);
});
