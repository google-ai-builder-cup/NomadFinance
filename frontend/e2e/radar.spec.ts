import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signedInWorker } from "./support/emulators";
import { type FakeRadar, radarApi, seedEntity } from "./support/radarApi";

// Exploitation Radar in a real browser (NF-HR-006): the map, a business's profile, and the report
// form. The API is a stand-in (support/radarApi.ts); the English copy is in src/i18n/en.json.

let api: FakeRadar;
const unique = Math.random().toString(36).slice(2, 8);

test.beforeEach(async ({ page }) => {
  api = await radarApi(page);
  await signedInWorker(page);
});

async function chooseRoute(page: Page, label: RegExp): Promise<void> {
  const options = await page
    .locator("#radar-location option")
    .evaluateAll((all) =>
      all.map((option) => [(option as HTMLOptionElement).value, option.textContent ?? ""])
    );
  const hit = options.find(([value, text]) => value && label.test(text));
  if (!hit) {
    throw new Error(`no route like ${label}`);
  }
  await page.locator("#radar-location").selectOption(hit[0]);
}

async function writeReport(page: Page, name: string, text: string): Promise<void> {
  await page.goto("/radar/report");
  await page.getByLabel("Money transfer service").check();
  await page.locator("#radar-entity-name").fill(name);
  await page.getByRole("button", { name: "Next" }).click();
  await chooseRoute(page, /Singapore → India/);
  await page.getByRole("button", { name: "Next" }).click();
  await page.locator("#radar-description").fill(text);
  await page.getByRole("button", { name: "Next" }).click();
}

test("a business reported twice shows on its route and opens a profile that says it is flagged", async ({
  page,
}) => {
  const slug = `qa-remit-${unique}`;
  await seedEntity({ slug, name: `Qa Remit ${unique}`, reports: 3, incidents: 2, flagged: true });

  await page.goto("/radar/heatmap");
  await expect(page.getByRole("heading", { name: "Exploitation Radar" })).toBeVisible();
  await page.getByRole("button", { name: /Singapore → India/ }).click();
  await page.locator(`a[href="/radar/entity/${slug}"]`).locator("visible=true").first().click();

  await expect(page.getByRole("heading", { name: `Qa Remit ${unique}` })).toBeVisible();
  await expect(page.getByText("Community flagged").first()).toBeVisible();
  await expect(page.getByText("The app showed a fee of 3 SGD")).toBeVisible();
  await page.getByRole("link", { name: "Back to map" }).click();
  await expect(page.getByRole("heading", { name: "Exploitation Radar" })).toBeVisible();
});

test("a business nobody has reported says so and leaves a way back", async ({ page }) => {
  await page.goto("/radar/entity/nobody-has-reported-this");
  await expect(page.getByText("We could not find this business.")).toBeVisible();
  await expect(page.getByRole("link", { name: "Back to map" })).toBeVisible();
});

test("each step of the report form asks for its answer", async ({ page }) => {
  await page.goto("/radar/report");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Choose who you are reporting.")).toBeVisible();
  await page.getByLabel("Money transfer service").check();
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Write the name of the business.")).toBeVisible();
  await page.locator("#radar-entity-name").fill(`Qa Remit ${unique}`);
  await page.getByRole("button", { name: "Next" }).click();
  await page.locator("#radar-location").selectOption("");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText("Choose where it happened.")).toBeVisible();
  await chooseRoute(page, /Singapore → India/);
  await page.getByRole("button", { name: "Next" }).click();
  await page.locator("#radar-description").fill("short");
  await page.getByRole("button", { name: "Next" }).click();
  await expect(page.getByText(/Write at least \d+ characters/)).toBeVisible();
  expect(api.calls).toHaveLength(0);
});

test("a report is sent once with what was written, and thanks the worker", async ({ page }) => {
  await writeReport(
    page,
    `Qa Remit ${unique}`,
    "A fee was added at the counter that the app did not show."
  );
  await page.getByRole("button", { name: "Send report" }).click();

  await expect(page.getByText("Thank you. Your report was received.")).toBeVisible();
  const sent = api.to("POST", /\/report$/);
  expect(sent).toHaveLength(1);
  expect(sent[0].body).toMatchObject({
    entity_type: "money_transfer_operator",
    entity_name: `Qa Remit ${unique}`,
    corridor_id: "SG-IN",
    description: "A fee was added at the counter that the app did not show.",
  });
});

test("two taps on Send report in the same instant send one report (QA-C-01)", async ({ page }) => {
  api.reportTakes(600);
  await writeReport(
    page,
    `Qa Twice ${unique}`,
    "A service charge was taken that the receipt did not list."
  );

  await page.getByRole("button", { name: "Send report" }).dblclick();

  await expect(page.getByText("Thank you. Your report was received.")).toBeVisible();
  expect(api.to("POST", /\/report$/)).toHaveLength(1);
});

for (const [status, detail, shown] of [
  [422, "spam", "This does not look like a real report. Please describe what happened."],
  [
    422,
    "abusive",
    "This report cannot be published as written. Remove any threats or abusive words.",
  ],
  [
    422,
    "personal",
    "Please remove personal details (names of people, phone numbers, addresses) and try again.",
  ],
  [503, "busy", "The AI service is busy right now. Please try again in a minute."],
  [504, "slow", "The AI service took too long to answer. Please try again."],
] as const) {
  test(`a report the server refuses (${status} ${detail}) says why and can be sent again`, async ({
    page,
  }) => {
    const detailText: Record<string, string> = {
      spam: "This doesn't look like a real report. Please describe what happened.",
      abusive:
        "This report cannot be published as written. Remove any threats or abusive language.",
      personal: "Please remove personal details (names, phone numbers, addresses) and try again.",
    };
    api.reportWill({ status, detail: detailText[detail] ?? detail });
    await writeReport(
      page,
      `Qa Refused ${unique}`,
      "A fee was added at the counter that the app did not show."
    );
    await page.getByRole("button", { name: "Send report" }).click();
    await expect(page.getByText(shown)).toBeVisible();

    api.reportWill("ok");
    await page.getByRole("button", { name: "Send report" }).click();
    await expect(page.getByText("Thank you. Your report was received.")).toBeVisible();
    expect(api.to("POST", /\/report$/)).toHaveLength(2);
  });
}

test("the Radar pages do not scroll sideways", async ({ page }) => {
  const slug = `qa-wide-${unique}`;
  await seedEntity({ slug, name: `Qa Wide ${unique}`, reports: 2, incidents: 2, flagged: true });
  for (const path of [
    "/radar/heatmap",
    "/radar/report",
    "/radar/alerts",
    `/radar/entity/${slug}`,
  ]) {
    await page.goto(path);
    await expect(page.locator("main h1").first()).toBeVisible();
    await page.waitForTimeout(800); // the map draws after its data
    const overflow = await page.evaluate(
      () => document.documentElement.scrollWidth - document.documentElement.clientWidth
    );
    expect(overflow, path).toBeLessThanOrEqual(1);
  }
});
