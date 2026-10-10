import { expect, type Page, test } from "@playwright/test";

import { signedInWorker, type TestUser } from "./support/emulators";
import { fibApi, type FakeFib, seedFinancialProfile } from "./support/fibApi";
import { setDocument } from "./support/firestoreRest";
import { mockApi } from "./support/mockApi";
import { tap } from "./support/tap";

// Financial Identity in a real browser (NF-HR-004): the dashboard with and without a score, the
// log forms and what they refuse, the bill photo, sorting bills, and the PDF export. The backend
// is a stand-in (support/fibApi.ts) that writes the documents the real one writes. The English
// copy is in src/i18n/en.json; a copy change means changing it here.

let fib: FakeFib;
let user: TestUser;

test.beforeEach(async ({ page }) => {
  await mockApi(page);
  user = await signedInWorker(page);
  fib = await fibApi(page, user);
});

const daysAgo = (days: number) => {
  const date = new Date();
  date.setDate(date.getDate() - days);
  return date.toISOString().slice(0, 10);
};

async function openLog(page: Page, tab: "Income" | "Bill" | "Savings" | "Transfer") {
  await page.goto("/identity/log");
  const choice = page.getByRole("tab", { name: tab, exact: true });
  await expect(choice).toBeVisible({ timeout: 15_000 });
  await tap(choice);
}

const submit = (page: Page) => tap(page.getByRole("button", { name: "Log it", exact: true }));

test("a new worker sees calm empty states, not errors", async ({ page }) => {
  await page.goto("/identity");

  await expect(
    page.getByRole("heading", { level: 1, name: "Your Financial Identity" })
  ).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/score isn't ready yet/)).toBeVisible();
  await expect(page.getByText("Log some income and bills to see this chart.")).toBeVisible();
  await expect(page.getByRole("alert")).toHaveCount(0);
});

test("with a stored profile the dashboard shows the score, the four indicators and the chart", async ({
  page,
}) => {
  await seedFinancialProfile(user);
  for (const [index, amount] of [2000, 2000, 2100].entries()) {
    await setDocument(`users/${user.uid}/income/seed${index}`, {
      entry_date: daysAgo(10 + index * 30),
      amount,
      currency: "SGD",
      category: "salary",
      category_source: "user",
      verified: false,
      source: "manual",
      created_at: new Date(),
      schema_version: 1,
    });
  }
  await page.goto("/identity");

  await expect(page.getByText("78", { exact: true }).first()).toBeVisible({ timeout: 15_000 });
  for (const name of [
    "Income stability",
    "Savings rate",
    "Sending money home",
    "Paying bills on time",
  ]) {
    await expect(page.getByText(name).first()).toBeVisible();
  }
  await expect(page.getByRole("heading", { name: "Income and expenses" })).toBeVisible();
  await expect(page.locator("svg.recharts-surface").first()).toBeVisible();
});

test("income is logged with the amount as typed, in the worker's currency", async ({ page }) => {
  await openLog(page, "Income");
  await page.getByLabel("Amount", { exact: true }).fill("1,000.50");
  await page.getByLabel("Category").selectOption("salary");
  await page.getByLabel("Employer (optional)").fill("Tan Family");
  await submit(page);

  await expect(page.getByText("Logged.").first()).toBeVisible();
  const [call] = fib.to("POST", /\/income$/);
  expect(call.body).toMatchObject({
    amount: 1000.5,
    category: "salary",
    employer_name: "Tan Family",
  });
});

for (const [typed, message] of [
  ["", "Enter an amount."],
  ["abc", "Enter a valid amount."],
  ["-5", "Enter a valid amount."],
  ["0", "Enter a valid amount."],
  ["1e3", "Enter a valid amount."],
] as const) {
  test(`income '${typed}' is refused with a plain message and nothing is sent`, async ({
    page,
  }) => {
    await openLog(page, "Income");
    await page.getByLabel("Category").selectOption("salary");
    await page.getByLabel("Amount", { exact: true }).fill(typed);
    await submit(page);

    await expect(page.getByRole("alert")).toContainText(message);
    expect(fib.to("POST", /\/income$/)).toHaveLength(0);
  });
}

test("an amount no entry could be is refused: a slipped finger must not reach the profile", async ({
  page,
}) => {
  await openLog(page, "Income");
  await page.getByLabel("Category").selectOption("salary");
  await page.getByLabel("Amount", { exact: true }).fill("99999999999999");
  await submit(page);

  await expect(page.getByRole("alert")).toContainText("That amount is too large.");
  expect(fib.to("POST", /\/income$/)).toHaveLength(0);
});

test("income with no category, or with more decimals than the currency has, is refused", async ({
  page,
}) => {
  await openLog(page, "Income");
  await page.getByLabel("Amount", { exact: true }).fill("50");
  await page.getByLabel("Category").selectOption("");
  await submit(page);
  await expect(page.getByRole("alert")).toContainText("Choose a category.");

  await page.getByLabel("Category").selectOption("salary");
  await page.getByLabel("Currency").selectOption("JPY");
  await page.getByLabel("Amount", { exact: true }).fill("10.5");
  await submit(page);
  await expect(page.getByRole("alert")).toContainText("Too many decimal places for this currency.");
  expect(fib.to("POST", /\/income$/)).toHaveLength(0);
});

test("savings can be put in and taken out", async ({ page }) => {
  await openLog(page, "Savings");
  await page.getByLabel("Amount", { exact: true }).fill("300");
  await submit(page);
  await expect(page.getByText("Logged.").first()).toBeVisible();

  await page.getByText("Money out", { exact: true }).click();
  await page.getByLabel("Amount", { exact: true }).fill("100");
  await submit(page);

  await expect.poll(() => fib.to("POST", /\/savings$/).length).toBe(2);
  const bodies = fib.to("POST", /\/savings$/).map((call) => call.body);
  expect(bodies[0]).toMatchObject({ amount: 300, direction: "deposit" });
  expect(bodies[1]).toMatchObject({ amount: 100, direction: "withdrawal" });
});

test("a transfer is explained, with the way to Remittance X-Ray", async ({ page }) => {
  await openLog(page, "Transfer");

  await tap(page.getByRole("link", { name: /Go to Remittance X-Ray/ }));
  await expect(page).toHaveURL(/\/remittance$/);
});

test("a bill with no category waits to be sorted, and 'Sort my bills' sorts it", async ({
  page,
}) => {
  await openLog(page, "Bill");
  await tap(page.getByRole("tab", { name: "Type it in", exact: true }));
  await page.getByLabel("Amount", { exact: true }).fill("48.90");
  await page.getByLabel("Who billed you (optional)").fill("SP Services");
  await submit(page);
  await expect(page.getByText("Logged.").first()).toBeVisible();

  await page.goto("/identity");
  await expect(page.getByText(/Bills without a category: 1/)).toBeVisible({ timeout: 15_000 });
  await tap(page.getByRole("button", { name: "Sort my bills", exact: true }));

  await expect(page.getByText(/Sorted: 1\. Still to sort: 0\./)).toBeVisible();
  expect(fib.to("POST", /\/categorize$/)).toHaveLength(1);
});

for (const [outcome, message] of [
  ["not_a_bill", "No bill found. Upload a clear photo or PDF of the bill or receipt."],
  [
    "unreadable",
    "The amount or currency could not be read. Take a clearer photo with the whole bill in view, or enter it by hand.",
  ],
] as const) {
  test(`a bill photo the reader calls '${outcome}' says so and logs nothing`, async ({ page }) => {
    fib.scanWill(outcome);
    await openLog(page, "Bill");
    await page
      .locator('input[type="file"]')
      .first()
      .setInputFiles({
        name: "bill.jpg",
        mimeType: "image/jpeg",
        buffer: Buffer.from([0xff, 0xd8, 0xff, 0xd9]),
      });
    await tap(page.getByRole("button", { name: "Read and log this bill", exact: true }));

    await expect(page.getByText(message)).toBeVisible();
    await expect(page.getByText("Logged.")).toHaveCount(0);
  });
}

test("a readable bill photo is logged", async ({ page }) => {
  await openLog(page, "Bill");
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "bill.jpg",
      mimeType: "image/jpeg",
      buffer: Buffer.from([0xff, 0xd8, 0xff, 0xd9]),
    });
  await tap(page.getByRole("button", { name: "Read and log this bill", exact: true }));

  await expect(page.getByText("Logged.").first()).toBeVisible();
  expect(fib.to("POST", /\/bill\/scan$/)).toHaveLength(1);
});

test("a file that is not a bill is refused before it is sent", async ({ page }) => {
  await openLog(page, "Bill");
  await page
    .locator('input[type="file"]')
    .first()
    .setInputFiles({
      name: "notes.txt",
      mimeType: "text/plain",
      buffer: Buffer.from("hello"),
    });

  await expect(page.getByText("Use a PDF, PNG, JPEG, WebP or HEIC file.")).toBeVisible();
  expect(fib.to("POST", /\/bill\/scan$/)).toHaveLength(0);
});

test("without a score yet, the export page explains what to do instead of offering a PDF", async ({
  page,
}) => {
  await page.goto("/identity/export");

  await expect(page.getByRole("heading", { level: 1, name: "Export your report" })).toBeVisible({
    timeout: 15_000,
  });
  await expect(page.getByText(/score isn't ready yet/)).toBeVisible();
  await expect(page.getByRole("button", { name: "Generate PDF", exact: true })).toHaveCount(0);
});

test("a PDF is generated, previewed and offered for download", async ({ page }) => {
  await seedFinancialProfile(user);
  await page.goto("/identity/export");

  await expect(page.getByText("You haven't generated a report yet.")).toBeVisible({
    timeout: 15_000,
  });
  await page.getByLabel("Name on the report (optional)").fill("Priya Test");
  await tap(page.getByRole("button", { name: "Generate PDF", exact: true }));

  await expect(
    page
      .getByRole("link", { name: /Download/ })
      .or(page.getByRole("button", { name: /Download/ }))
      .first()
  ).toBeVisible();
  const [call] = fib.to("POST", /\/report\/export$/);
  expect(call.body).toMatchObject({ holder_name: "Priya Test" });

  await tap(page.getByRole("button", { name: "Preview" }));
  const preview = page.getByRole("dialog");
  await expect(preview).toContainText("Months of data");
  await expect(preview).toContainText("This is not a credit score");
  await page.keyboard.press("Escape");
  await expect(preview).toBeHidden();
});
