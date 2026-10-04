import { afterEach, describe, expect, it, vi } from "vitest";

import i18n, { setLanguage } from "@/lib/i18n";

// A language file that cannot be fetched (no signal, never cached) must not leave the UI
// showing raw keys.
vi.mock("@/i18n/tl.json", () => {
  throw new Error("Failed to fetch dynamically imported module");
});

afterEach(async () => {
  await setLanguage("en");
});

describe("setLanguage", () => {
  it("starts with English only and fetches another language on first use", async () => {
    expect(i18n.hasResourceBundle("hi", "translation")).toBe(false);

    await setLanguage("hi");

    expect(i18n.resolvedLanguage).toBe("hi");
    expect(i18n.t("common.loading")).not.toBe("Loading…");
    expect(i18n.hasResourceBundle("hi", "translation")).toBe(true);
  });

  it("switches back to English without a fetch", async () => {
    await setLanguage("hi");
    await setLanguage("en");

    expect(i18n.resolvedLanguage).toBe("en");
    expect(i18n.t("common.loading")).toBe("Loading…");
  });

  it("stays in the current language when the file cannot be fetched", async () => {
    await setLanguage("tl");

    expect(i18n.resolvedLanguage).toBe("en");
    expect(i18n.t("common.loading")).toBe("Loading…");
  });
});
