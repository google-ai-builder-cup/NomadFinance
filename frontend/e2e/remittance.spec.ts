import { expect, test } from "@playwright/test";

import { signedInWorker, type TestUser } from "./support/emulators";
import { setDocument } from "./support/firestoreRest";
import { type FakeRemittance, remittanceApi } from "./support/remittanceApi";

// Remittance X-Ray in a real browser (NF-HR-005): compare, the amount field, the advice, logging a
// transfer. The prices are a stand-in (support/remittanceApi.ts); the English copy is in
// src/i18n/en.json. The Scam Analyzer's browser tests are in scam-check.spec.ts.

let api: FakeRemittance;
let worker: TestUser;

test.beforeEach(async ({ page }) => {
  api = await remittanceApi(page);
  worker = await signedInWorker(page);
  await page.goto("/remittance");
  await expect(page.getByRole("heading", { level: 1, name: "Send money home" })).toBeVisible();
});

const amount = (page: import("@playwright/test").Page) => page.locator("#remittance-amount");
const compare = (page: import("@playwright/test").Page) =>
  page.getByRole("button", { name: "Compare services" });

test("an amount is compared and the services are ranked", async ({ page }) => {
  await amount(page).fill("500");
  await compare(page).click();

  await expect(page.getByText("Services compared: 3")).toBeVisible();
  await expect(page.locator("main").getByText("Sending SGD 500 to India").first()).toBeVisible();
  expect(api.to("POST", /\/compare$/)).toHaveLength(1);
  expect(api.to("POST", /\/compare$/)[0].body).toEqual({ corridor_id: "SG-IN", amount: 500 });
});

test("an amount typed with Hindi or Bengali digits is read as the number it is (QA-B-01)", async ({
  page,
}) => {
  await amount(page).fill("५००");
  await compare(page).click();
  await expect(page.getByText("Services compared: 3")).toBeVisible();
  expect(api.to("POST", /\/compare$/)[0].body).toEqual({ corridor_id: "SG-IN", amount: 500 });

  await amount(page).fill("৬৪৫");
  await compare(page).click();
  await expect.poll(() => api.to("POST", /\/compare$/).length).toBe(2);
  expect(api.to("POST", /\/compare$/)[1].body).toEqual({ corridor_id: "SG-IN", amount: 645 });
});

test("a number that is not an amount is told so and nothing is sent", async ({ page }) => {
  for (const [text, message] of [
    ["abc", "Enter the amount as a number"],
    ["0", "Enter the amount as a number"],
    ["99999999", "Enter at most"],
    ["", "Enter the amount you want to send"],
  ] as const) {
    await amount(page).fill(text);
    await compare(page).click();
    await expect(page.getByRole("alert").filter({ hasText: message })).toBeVisible();
  }
  expect(api.calls).toHaveLength(0);
});

test("two quick taps on 'I used this' log one transfer (QA-B-03)", async ({ page }) => {
  await amount(page).fill("500");
  await compare(page).click();
  await expect(page.getByText("Services compared: 3")).toBeVisible();

  const log = page.getByRole("button", { name: "I used this" }).locator("visible=true").first();
  await log.evaluate((button) => {
    (button as HTMLButtonElement).click();
    (button as HTMLButtonElement).click();
  });

  await expect(
    page.getByText("Logged", { exact: true }).locator("visible=true").first()
  ).toBeVisible();
  expect(api.to("POST", /\/log$/)).toHaveLength(1);
});

test("the advice shows, and a failed advice does not talk about a contract (QA-B-02)", async ({
  page,
}) => {
  await amount(page).fill("500");
  await compare(page).click();
  await expect(page.getByText("Services compared: 3")).toBeVisible();

  api.adviceWill(502);
  await page.getByRole("button", { name: "Get advice" }).click();
  const alert = page.getByRole("alert").filter({ hasText: /./ }).last();
  await expect(alert).toContainText("Our server had a problem");
  await expect(page.locator("main")).not.toContainText("your contract");

  api.adviceWill("ok");
  await page.getByRole("button", { name: "Get advice" }).click();
  await expect(page.getByText("Wise gives your family the most.")).toBeVisible();
  // The comparison stays under the advice either way.
  await expect(page.getByText("Services compared: 3")).toBeVisible();
});

test("busy and slow advice keep their own words", async ({ page }) => {
  await amount(page).fill("500");
  await compare(page).click();
  await expect(page.getByText("Services compared: 3")).toBeVisible();

  api.adviceWill(503);
  await page.getByRole("button", { name: "Get advice" }).click();
  await expect(page.getByText("The AI service is busy right now")).toBeVisible();

  api.adviceWill(504);
  await page.getByRole("button", { name: "Get advice" }).click();
  await expect(page.getByText("The AI service took too long")).toBeVisible();
});

test("a link from a plan runs the comparison once; a bad link runs nothing", async ({ page }) => {
  await page.goto("/remittance?corridor=SG-IN&amount=500");
  await expect(page.getByText("Services compared: 3")).toBeVisible();
  expect(api.to("POST", /\/compare$/)).toHaveLength(1);

  await page.goto("/remittance?corridor=XX&amount=-1");
  await expect(page.getByRole("heading", { level: 1, name: "Send money home" })).toBeVisible();
  await page.goto("/remittance?corridor=SG-IN&amount=9999999");
  await expect(page.getByRole("heading", { level: 1, name: "Send money home" })).toBeVisible();
  expect(api.to("POST", /\/compare$/)).toHaveLength(1);
});

test("the results do not scroll the page sideways", async ({ page }) => {
  await amount(page).fill("500");
  await compare(page).click();
  await expect(page.getByText("Services compared: 3")).toBeVisible();

  const overflow = await page.evaluate(
    () => document.documentElement.scrollWidth - document.documentElement.clientWidth
  );
  expect(overflow).toBeLessThanOrEqual(0);
});

test("an amount that could be read two ways says how it was read before it is sent", async ({
  page,
}) => {
  await amount(page).fill("1.500");

  await expect(page.getByRole("status").filter({ hasText: "We read this as" })).toContainText(
    "1,500"
  );
  await amount(page).fill("1.5");
  await expect(page.getByRole("status").filter({ hasText: "We read this as" })).toHaveCount(0);
});

test("the transfers a worker logged are listed, newest first", async ({ page }) => {
  const entry = (day: string, firm: string, sent: number) => ({
    entry_date: day,
    corridor_id: "SG-IN",
    provider_name: firm,
    provider_rpw_id: 101,
    send_amount: sent,
    send_currency: "SGD",
    receive_amount: sent * 61,
    receive_currency: "INR",
    fee: 4.5,
    cost_pct: 1.2,
    source: "remittance_xray",
  });
  await setDocument(`users/${worker.uid}/transfers/t1`, entry("2026-09-12", "Remitly", 400));
  await setDocument(`users/${worker.uid}/transfers/t2`, entry("2026-10-12", "Wise", 500));

  await page.getByRole("link", { name: "My logged transfers" }).click();

  await expect(page.getByRole("heading", { name: "Money you sent" })).toBeVisible();
  const rows = page.getByRole("listitem").filter({ hasText: "SG → IN" });
  await expect(rows).toHaveCount(2);
  await expect(rows.first()).toContainText("Wise");
  await expect(rows.nth(1)).toContainText("Remitly");
});
