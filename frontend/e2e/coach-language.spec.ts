import { expect, test } from "@playwright/test";

import { coachApi, coachText, type FakeCoach } from "./support/coachApi";
import { answer, conversation, expectAsked, panel } from "./support/coachSteps";
import { signedInWorker } from "./support/emulators";

// Changing the coach's language half way (NF-FC-018, NF-FC-025): the coach carries on in the new
// language from the question it was asking, with every answer and the step kept, and the worker's
// next answer goes in that language. Hindi is the language of the mock stream this follows
// (docs/mocks/coach/turn-08-language-switch.sse).

let coach: FakeCoach;

test.beforeEach(async ({ page }) => {
  coach = await coachApi(page);
  await signedInWorker(page);
  await page.goto("/coach");
  await expectAsked(page, "destination_country");
  await answer(page, "destination_country", "recruitment_fee_paid");
});

test("switching to Hindi keeps the answers and the step, and the coach asks again in Hindi", async ({
  page,
}) => {
  const answered = Object.keys(coach.session().slots);
  expect(answered).toHaveLength(6);

  await page.getByLabel("Coach language").selectOption("hi");

  // The switch is a turn with no words of the worker's: the coach asks the same question again.
  const talk = conversation(page, "hi");
  await expect(talk.getByText("ठीक है, अब मैं हिंदी में बात करूँगा।")).toBeVisible();
  await expect(talk.getByText(/एजेंट या रिक्रूटर को कितना पैसा दिया है/)).toBeVisible();
  const switchTurn = coach.turns().at(-1);
  expect(switchTurn?.body).toEqual({ language: "hi" });

  // Nothing was lost: the same answers, the same step, the same question.
  expect(Object.keys(coach.session().slots)).toEqual(answered);
  expect(coach.session().stage).toBe("debt");
  expect(coach.session().next_slot).toBe("recruitment_fee_paid");
  expect(coach.session().language).toBe("hi");
  await expect(page.getByLabel(coachText("hi", "language.label"))).toHaveValue("hi");

  // The helper is in Hindi now, and the answer it writes goes to the server in Hindi.
  const helper = panel(page, "hi");
  await helper.getByLabel(coachText("hi", "input.amountLabel"), { exact: true }).fill("150000");
  await helper.getByLabel(coachText("hi", "input.currencyLabel")).selectOption("INR");
  await helper.getByRole("button", { name: coachText("hi", "input.send"), exact: true }).click();

  await expect(talk.getByText(/क्या आप पर इस सफ़र के लिए अब भी कर्ज़ बाकी है/)).toBeVisible();
  const sent = coach.turns().at(-1);
  expect(sent?.body.language).toBe("hi");
  expect(sent?.body.text).toContain("150000");
  expect(sent?.body.text).toContain("INR");
  expect(coach.session().next_slot).toBe("debt_outstanding");
});

test("the language chosen on the coach screen is the language of the whole app", async ({
  page,
}) => {
  await page.getByLabel("Coach language").selectOption("hi");

  await expect(page.getByRole("heading", { level: 1 })).toHaveText(coachText("hi", "home.title"));
  expect(await page.evaluate(() => document.documentElement.lang)).toBe("hi");
});
