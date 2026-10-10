import { expect, type Page, test } from "@playwright/test";

import { coachApi } from "./support/coachApi";
import { contractApi, seedCompletedContract } from "./support/contractApi";
import { signedInWorker } from "./support/emulators";
import { fibApi, seedFinancialProfile } from "./support/fibApi";
import { allKeys, appText, coachString, LANGUAGES, type Language } from "./support/i18n";
import { mockApi } from "./support/mockApi";

// Each of the six languages, spot-checked on the screens of Contract Shield, Financial Identity
// and the Coach (NF-HR-004): the page speaks that language, shows no untranslated key or empty
// placeholder, and does not scroll sideways at this screen size (a phone and a desktop run it).
// The unit tests hold every language to the same keys; this holds the screens to what they show.

const KEYS = allKeys();

test.setTimeout(120_000);

async function inLanguage(page: Page, language: Language) {
  await page.addInitScript((code) => {
    // A signed-in worker's quick switch, as the header's language picker leaves it.
    sessionStorage.setItem("nomadfinance.sessionLanguage", code);
  }, language);
}

async function expectScreen(page: Page, language: Language, route: string, heading: string) {
  await page.goto(route);
  await expect(
    page.getByRole("heading", { level: 1 }).filter({ hasText: heading }).first()
  ).toBeVisible({ timeout: 20_000 });
  // Give the data of the screen a moment to arrive and settle, so what is checked is the whole page.
  await page.waitForTimeout(800);

  const facts = await page.evaluate(() => ({
    lang: document.documentElement.lang,
    overflow: document.documentElement.scrollWidth - document.documentElement.clientWidth,
    text: document.body.innerText,
  }));
  expect(facts.lang, `${route}: the page language`).toBe(language);
  expect(facts.overflow, `${route}: the page scrolls sideways`).toBeLessThanOrEqual(0);
  const untranslated = KEYS.filter((key) => facts.text.includes(key));
  expect(untranslated, `${route}: keys shown instead of text`).toEqual([]);
  expect(facts.text, `${route}: an empty placeholder`).not.toMatch(
    /\{\{[^}]*\}\}|\[object Object\]|\bundefined\b|\bNaN\b/
  );
}

for (const language of LANGUAGES) {
  test(`Contract Shield and Financial Identity speak ${language}`, async ({ page }) => {
    await inLanguage(page, language);
    await mockApi(page);
    const user = await signedInWorker(page);
    await contractApi(page, user);
    await fibApi(page, user);
    await seedFinancialProfile(user, language);
    const contractId = await seedCompletedContract(user);

    const t = (key: string) => appText(language, key);
    await expectScreen(page, language, "/contract", t("contract.upload.title"));
    await expectScreen(page, language, "/contract/history", t("contract.history.title"));
    await expectScreen(page, language, `/contract/${contractId}`, "Employment contract");
    await expect(page.getByText(t("contract.complaint.heading")).first()).toBeVisible();
    await expectScreen(page, language, "/identity", t("fib.dashboard.title"));
    await expectScreen(page, language, "/identity/log", t("fib.log.title"));
    await expectScreen(page, language, "/identity/export", t("fib.export.title"));
  });

  test(`the Coach speaks ${language}`, async ({ page }) => {
    await inLanguage(page, language);
    await coachApi(page);
    await signedInWorker(page);

    await expectScreen(page, language, "/coach", coachString(language, "home.title"));
  });
}
