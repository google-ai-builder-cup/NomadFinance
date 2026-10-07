import { expect, test } from "@playwright/test";

import { signedInWorker } from "./support/emulators";
import { type MockApi, mockApi, mockBody } from "./support/mockApi";

// The scam check flow in a real browser (NF-SA-020): a signed-in worker pastes a message, reads
// the verdict and the explanation, and warns other workers. Sign-in is through the Auth
// emulator and the backend's answers come from docs/mocks/scam/, so the run needs no Gemini and
// is the same every time. The English copy is in src/i18n/scam/en.json.

const MESSAGE =
  "Congratulations! You are selected for a caregiver job in Singapore. Pay 800 SGD processing fee today or the visa slot is cancelled.";

interface AnalyzeAnswer {
  explainer: { scammer_wants: string; next_steps: string[] };
  indicators: { id: string }[];
}

let api: MockApi;

test.beforeEach(async ({ page }) => {
  api = await mockApi(page);
  await signedInWorker(page);
  await page.goto("/scam-check");
  await expect(page.getByRole("heading", { level: 1, name: "Scam check" })).toBeVisible();
});

async function paste(page: import("@playwright/test").Page, text: string) {
  await page.getByLabel("The message you received").fill(text);
  await page.getByRole("button", { name: "Check this message" }).click();
}

test("paste a scam, read the verdict and the explanation, then warn other workers", async ({
  page,
}) => {
  const answer = mockBody<AnalyzeAnswer>("scam/analyze-01-high-risk.json");

  await paste(page, MESSAGE);

  await expect(page.getByRole("heading", { name: "This looks like a scam" })).toBeVisible();
  await expect(page.getByText("High risk").first()).toBeVisible();
  // The explanation the backend wrote (in the worker's language) and its next steps.
  await expect(page.getByText(answer.explainer.scammer_wants)).toBeVisible();
  for (const step of answer.explainer.next_steps) {
    await expect(page.getByText(step)).toBeVisible();
  }

  const [sent] = api.to("POST", /\/scam\/analyze$/);
  expect(sent.contentType).toContain("application/json");
  expect(sent.body).toEqual({ text: MESSAGE, language: "en", corridor_id: "SG-IN" });

  await page.getByRole("button", { name: "Warn other workers" }).click();
  const sheet = page.getByRole("dialog", { name: "Warn other workers" });
  await expect(sheet).toBeVisible();
  await sheet.getByRole("button", { name: "Send warning" }).click();

  await expect(page.getByText("Thank you. Other workers can now see your warning.")).toBeVisible();
  await expect(page.getByRole("link", { name: "See it in Radar" })).toHaveAttribute(
    "href",
    "/radar/entity/scam-illegal-recruitment-fee"
  );
  const [report] = api.to("POST", /\/checks\/k_01\/report$/);
  expect(report.body).toMatchObject({ indicator_ids: answer.indicators.map((i) => i.id) });
});

test("a message that is not a scam gets a reassurance and no warning button", async ({ page }) => {
  api.answerAnalyzeWith("scam/analyze-04-benign.json");

  await paste(page, "Your parcel arrives tomorrow between 9 and 12.");

  await expect(page.getByRole("heading", { name: "This does not look like a scam" })).toBeVisible();
  await expect(page.getByText("No scam found").first()).toBeVisible();
  await expect(page.getByRole("button", { name: "Warn other workers" })).toHaveCount(0);
});

test("a worker over the hourly limit is told how long to wait and keeps their message", async ({
  page,
}) => {
  api.answerAnalyzeWith("scam/analyze-error-rate-limited.json");

  await paste(page, MESSAGE);

  await expect(page.getByRole("alert")).toContainText("Try again in about 23 min");
  await expect(page.getByRole("button", { name: "Try again" })).toHaveCount(0);
  await expect(page.getByLabel("The message you received")).toHaveValue(MESSAGE);
});

test("a message over 4,000 characters cannot be sent, and is not cut", async ({ page }) => {
  const long = "a".repeat(4001);

  await page.getByLabel("The message you received").fill(long);

  await expect(page.getByText("4001 / 4000")).toBeVisible();
  await expect(page.getByRole("button", { name: "Check this message" })).toBeDisabled();
  await expect(page.getByLabel("The message you received")).toHaveValue(long);
  expect(api.to("POST", /\/scam\/analyze$/)).toHaveLength(0);
});

test("a message shared into the app fills the box and waits for the worker", async ({ page }) => {
  await page.goto("/scam-check?text=Pay%20800%20SGD%20today");

  await expect(page.getByLabel("The message you received")).toHaveValue("Pay 800 SGD today");
  await expect(page.getByText(/We added the message you shared/)).toBeVisible();
  await expect(page).toHaveURL(/\/scam-check$/);
  expect(api.to("POST", /\/scam\/analyze$/)).toHaveLength(0);
});
