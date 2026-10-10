import { expect, test } from "@playwright/test";

import { contractApi, type FakeContracts } from "./support/contractApi";
import { signedInWorker, type TestUser } from "./support/emulators";
import { mockApi } from "./support/mockApi";
import { tap } from "./support/tap";

// Contract Shield in a real browser (NF-HR-004): a worker uploads a contract, follows the check,
// reads the report in their own language, and finds it again later. The backend is a stand-in
// (support/contractApi.ts) that writes the same Firestore documents the pipeline writes. The
// English copy is in src/i18n/en.json; a copy change means changing it here.

let contracts: FakeContracts;
let user: TestUser;

const EN_SUMMARY = "The employer keeps the passport and gives only one rest day a month.";
const TL_SUMMARY = `[tl] ${EN_SUMMARY}`;
const SAMPLE = {
  name: "employment-contract.pdf",
  mimeType: "application/pdf",
  buffer: Buffer.from("%PDF-1.4\n%sample\n"),
};

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  user = await signedInWorker(page);
  contracts = await contractApi(page, user);
});

async function chooseContract(page: import("@playwright/test").Page, file = SAMPLE) {
  await page.goto("/contract");
  await expect(page.getByRole("heading", { level: 1, name: "Check your contract" })).toBeVisible({
    timeout: 15_000,
  });
  await page.locator('input[type="file"]').first().setInputFiles(file);
}

const checkButton = (page: import("@playwright/test").Page) =>
  page.getByRole("button", { name: "Check my contract", exact: true });

test("a contract is checked, followed on screen, and ends on its report", async ({ page }) => {
  await chooseContract(page);
  await tap(checkButton(page));

  // The steps show while the check runs; the report replaces them.
  await expect(page.getByText("Checking your contract")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Your contract, checked" })).toBeVisible();

  await expect(
    page.getByRole("img", { name: /Contract health 25 out of 100: Serious concerns/ })
  ).toBeVisible();
  await expect(page.getByText(EN_SUMMARY)).toBeVisible();
  await expect(page.getByRole("heading", { name: "Clause by clause" })).toBeVisible();
  await expect(page.getByRole("heading", { name: "Complaint letter" })).toBeVisible();
  expect(contracts.to("POST", /\/analyze$/)).toHaveLength(1);
});

test("the report can be read in another language: translated once, never asked for twice", async ({
  page,
}) => {
  await chooseContract(page);
  await tap(checkButton(page));
  await expect(page.getByRole("heading", { name: "Your contract, checked" })).toBeVisible();

  const language = page.getByLabel("Report language");
  await language.selectOption("tl");
  await expect(page.getByText(TL_SUMMARY)).toBeVisible();
  expect(contracts.to("POST", /\/reports\/tl$/)).toHaveLength(1);

  await language.selectOption("en");
  await expect(page.getByText(EN_SUMMARY)).toBeVisible();
  await language.selectOption("tl");
  await expect(page.getByText(TL_SUMMARY)).toBeVisible();
  expect(contracts.to("POST", /\/reports\/tl$/)).toHaveLength(1);
});

test("a photo that is too unclear asks for a better one and is not analysed", async ({ page }) => {
  await page.unroute("**/api/v1/contracts**");
  contracts = await contractApi(page, user, { legibility: "poor" });

  await chooseContract(page);
  await tap(checkButton(page));

  await expect(page.getByRole("alert")).toContainText("The photo is too unclear to read");
  expect(contracts.to("POST", /\/analyze$/)).toHaveLength(0);
});

test("when the AI service is busy the page says where it stopped, and Try again finishes", async ({
  page,
}) => {
  contracts.failNextAnalysis(503);
  await chooseContract(page);
  await tap(checkButton(page));

  await expect(page.getByText("We couldn't finish checking your contract.")).toBeVisible();
  await expect(
    page.getByText("The AI service is busy right now. Please try again in a minute.")
  ).toBeVisible();

  await tap(page.getByRole("button", { name: "Try again", exact: true }));

  await expect(page.getByRole("heading", { name: "Your contract, checked" })).toBeVisible();
  expect(contracts.to("POST", /\/analyze$/)).toHaveLength(2);
  // Trying again does not upload the file a second time.
  expect(contracts.to("POST", /^\/api\/v1\/contracts$/)).toHaveLength(1);
});

test("a file that is not a PDF or photo, or is over 10 MB, is refused before anything is sent", async ({
  page,
}) => {
  await chooseContract(page, {
    name: "notes.txt",
    mimeType: "text/plain",
    buffer: Buffer.from("hello"),
  });
  await expect(page.getByText("Upload a PDF or a photo (PNG, JPEG, WebP or HEIC).")).toBeVisible();

  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "huge.pdf",
      mimeType: "application/pdf",
      buffer: Buffer.alloc(11 * 1024 * 1024, 65),
    });
  await expect(
    page.getByText("This file is larger than 10 MB. Choose a smaller file.")
  ).toBeVisible();

  await expect(checkButton(page)).toBeDisabled();
  expect(contracts.calls).toHaveLength(0);
});

test("Past checks lists the contract, and its report opens again after a reload", async ({
  page,
}) => {
  await chooseContract(page);
  await tap(checkButton(page));
  await expect(page.getByRole("heading", { name: "Your contract, checked" })).toBeVisible();

  await page.goto("/contract/history");
  await expect(page.getByRole("heading", { level: 1, name: "Your contracts" })).toBeVisible();
  const row = page.getByRole("link", { name: /Employment contract/ });
  await expect(row).toHaveCount(1);
  await tap(row);

  await expect(page).toHaveURL(/\/contract\/e2econtract\d+$/);
  await expect(page.getByRole("heading", { name: "Complaint letter" })).toBeVisible();
  await page.reload();
  await expect(page.getByRole("heading", { name: "Clause by clause" })).toBeVisible();
});

test("a contract number that is not the worker's own shows 'could not be found'", async ({
  page,
}) => {
  await page.goto("/contract/someone-elses-contract");

  await expect(page.getByText("This contract could not be found.")).toBeVisible();
  await expect(page.getByText("The employer keeps the passport")).toHaveCount(0);
});

test("losing the connection during an upload says so in plain words, and the next try works", async ({
  page,
}) => {
  await chooseContract(page);
  contracts.disconnect();
  await tap(checkButton(page));

  await expect(page.getByRole("alert")).toContainText("No internet connection");

  contracts.connect();
  await tap(checkButton(page));
  await expect(page.getByRole("heading", { name: "Your contract, checked" })).toBeVisible();
});

test("a contract from another country than the worker's profile is flagged, and can be checked again for it", async ({
  page,
}) => {
  await page.unroute("**/api/v1/contracts**");
  contracts = await contractApi(page, user, { detectedCountry: "KR" });
  await chooseContract(page);
  await tap(checkButton(page));

  const notice = page.getByRole("region", {
    name: /This contract looks like it is from South Korea/,
  });
  await expect(notice).toContainText("it was checked against Singapore labor law");
  await tap(notice.getByRole("button", { name: "Check it against South Korea law" }));

  await expect(page.getByRole("heading", { name: "Your contract, checked" })).toBeVisible();
  await expect(notice).toHaveCount(0);
  const [first, second] = contracts.to("POST", /\/analyze$/);
  expect(first.body).toMatchObject({ host_country: "SG" });
  expect(second.body).toMatchObject({ host_country: "KR" });
});

test("the same notice is on a past check opened from the history", async ({ page }) => {
  await page.unroute("**/api/v1/contracts**");
  contracts = await contractApi(page, user, { detectedCountry: "AU" });
  await chooseContract(page);
  await tap(checkButton(page));
  await expect(page.getByRole("heading", { name: "Your contract, checked" })).toBeVisible();

  await page.goto("/contract/history");
  await tap(page.getByRole("link", { name: /Employment contract/ }));

  const notice = page.getByRole("region", { name: /looks like it is from Australia/ });
  await expect(notice).toBeVisible();
  await tap(notice.getByRole("button", { name: "Check it against Australia law" }));
  await expect(notice).toHaveCount(0);
  expect(contracts.to("POST", /\/analyze$/).at(-1)?.body).toMatchObject({ host_country: "AU" });
});

test("a photo with no document in it says so, instead of 'Something went wrong'", async ({
  page,
}) => {
  await page.unroute("**/api/v1/contracts**");
  contracts = await contractApi(page, user, { notADocument: true });
  await chooseContract(page);
  await tap(checkButton(page));

  await expect(page.getByRole("alert")).toContainText("That doesn't look like a contract");
  expect(contracts.to("POST", /\/analyze$/)).toHaveLength(0);
});
