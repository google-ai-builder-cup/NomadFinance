import type { Locator } from "@playwright/test";

/**
 * Presses a control the way a person does on a phone: scrolled to the middle of the screen, clear
 * of the fixed bottom bar. Playwright's own scroll stops at the screen's edge, where that bar sits
 * over the control, so a plain `click()` finds the bar in the way.
 */
export async function tap(control: Locator): Promise<void> {
  await control.evaluate((element) =>
    element.scrollIntoView({ block: "center", behavior: "instant" })
  );
  await control.click();
}
