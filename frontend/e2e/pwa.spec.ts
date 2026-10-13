import { expect, test } from "@playwright/test";
import type { Page } from "@playwright/test";

import { signedInWorker } from "./support/emulators";
import { remittanceApi } from "./support/remittanceApi";

// The installed app (NF-HR-006): the manifest, the offer to install it, and what a worker sees when
// the signal goes. Service workers are blocked in this suite (playwright.config.ts), so the worker
// itself, the offline shell and push are covered by the regression sheet and the unit tests.

const OFFER = "Install NomadFinance: it opens faster and works offline.";
const IOS_STEPS = "To install NomadFinance, tap the Share button";

async function beforeInstallPrompt(page: Page, outcome: "accepted" | "dismissed" = "accepted") {
  await page.waitForSelector("#root > *");
  await page.waitForTimeout(800); // the app's own listener is attached once the first screen drew
  await page.evaluate((outcome) => {
    const event = new Event("beforeinstallprompt", { cancelable: true }) as Event & {
      prompt: () => Promise<void>;
      userChoice: Promise<{ outcome: string }>;
    };
    event.prompt = async () => {
      (window as unknown as { __prompted: number }).__prompted =
        ((window as unknown as { __prompted?: number }).__prompted ?? 0) + 1;
    };
    event.userChoice = Promise.resolve({ outcome });
    window.dispatchEvent(event);
  }, outcome);
}

test("the manifest makes an installable app with its three icons", async ({ request }) => {
  const response = await request.get("/manifest.webmanifest");
  expect(response.ok()).toBe(true);
  const manifest = (await response.json()) as {
    name: string;
    display: string;
    start_url: string;
    scope: string;
    icons: { src: string; sizes: string; purpose: string }[];
  };
  expect(manifest).toMatchObject({ name: "NomadFinance", display: "standalone", start_url: "/" });
  expect(manifest.icons.map((icon) => icon.purpose)).toContain("maskable");
  for (const icon of manifest.icons) {
    const file = await request.get(icon.src);
    expect(file.ok(), icon.src).toBe(true);
    const bytes = await file.body();
    expect(bytes.readUInt32BE(16), `${icon.src} width`).toBe(Number(icon.sizes.split("x")[0]));
  }
});

test.describe("the offer to install", () => {
  test.beforeEach(async ({ page, browserName }) => {
    // iOS has no install dialog: its offer is the Share steps, tested below.
    test.skip(browserName === "webkit", "iOS shows the Share steps instead of a dialog");
    await signedInWorker(page);
    await page.goto("/dashboard");
  });

  test("shows with an Install button, opens the browser's own dialog once, and goes", async ({
    page,
  }) => {
    await beforeInstallPrompt(page);
    await expect(page.getByText(OFFER)).toBeVisible({ timeout: 8000 });

    await page.getByRole("button", { name: "Install" }).click();

    await expect(page.getByText(OFFER)).toHaveCount(0);
    expect(
      await page.evaluate(() => (window as unknown as { __prompted: number }).__prompted)
    ).toBe(1);
  });

  test("closing it keeps it away for two weeks, and a refusal in the dialog does too", async ({
    page,
  }) => {
    await beforeInstallPrompt(page, "dismissed");
    await expect(page.getByText(OFFER)).toBeVisible({ timeout: 8000 });
    await page.getByRole("button", { name: "Install" }).click();
    await expect
      .poll(() => page.evaluate(() => localStorage.getItem("nomadfinance.installOfferDismissedAt")))
      .not.toBeNull();

    await page.reload();
    await beforeInstallPrompt(page);
    await page.waitForTimeout(4500);
    await expect(page.getByText(OFFER)).toHaveCount(0);

    await page.evaluate(() =>
      localStorage.setItem(
        "nomadfinance.installOfferDismissedAt",
        String(Date.now() - 15 * 24 * 3600 * 1000)
      )
    );
    await page.reload();
    await beforeInstallPrompt(page);
    await expect(page.getByText(OFFER)).toBeVisible({ timeout: 8000 });
  });

  test("goes when the app gets installed", async ({ page }) => {
    await beforeInstallPrompt(page);
    await expect(page.getByText(OFFER)).toBeVisible({ timeout: 8000 });
    await page.evaluate(() => window.dispatchEvent(new Event("appinstalled")));
    await expect(page.getByText(OFFER)).toHaveCount(0);
  });
});

test.describe("on an iPhone", () => {
  test.use({
    userAgent:
      "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1",
  });

  test("the offer is the Share steps, with no Install button", async ({ page }) => {
    await signedInWorker(page);
    await page.goto("/dashboard");

    await expect(page.getByText(IOS_STEPS)).toBeVisible({ timeout: 8000 });
    await expect(page.getByRole("button", { name: "Install" })).toHaveCount(0);
  });
});

test("a page that is open when the signal goes says so in plain words, and works again after", async ({
  page,
}) => {
  await remittanceApi(page);
  await signedInWorker(page);
  await page.goto("/remittance");
  await page.locator("#remittance-amount").fill("500");

  await page.route("**/api/v1/remittance/compare", (route) => route.abort("internetdisconnected"));
  await page.getByRole("button", { name: "Compare services" }).click();
  await expect(
    page.getByRole("alert").filter({ hasText: "No internet connection. Check your connection" })
  ).toBeVisible();

  await page.unroute("**/api/v1/remittance/compare");
  await page.getByRole("button", { name: "Compare services" }).click();
  await expect(page.getByText("Services compared: 3")).toBeVisible();
});
