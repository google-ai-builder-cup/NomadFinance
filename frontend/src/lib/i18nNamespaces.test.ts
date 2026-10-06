import { beforeEach, describe, expect, it, vi } from "vitest";

// One more language file that cannot be fetched: the coach's Tagalog strings.
vi.mock("@/i18n/coach/tl.json", () => {
  throw new Error("Failed to fetch dynamically imported module");
});

type I18nModule = typeof import("@/lib/i18n");
let lib: I18nModule;

// The module keeps which namespaces are in use, so each test starts from a fresh copy.
beforeEach(async () => {
  vi.resetModules();
  lib = await import("@/lib/i18n");
});

const has = (language: string, namespace: string) =>
  lib.default.hasResourceBundle(language, namespace);

describe("module namespaces", () => {
  it("download nothing until a page asks for them", async () => {
    await lib.setLanguage("hi");

    expect(has("en", "coach")).toBe(false);
    expect(has("hi", "coach")).toBe(false);
    expect(has("hi", "scam")).toBe(false);
  });

  it("load English and the current language when a page asks, and no other module", async () => {
    await lib.loadNamespace("coach");

    expect(has("en", "coach")).toBe(true);
    expect(has("hi", "coach")).toBe(false);
    expect(has("en", "scam")).toBe(false);
    expect(lib.default.t("home.title", { ns: "coach" })).toBe("Financial Coach");
  });

  it("reload only the namespaces in use when the language changes", async () => {
    await lib.loadNamespace("coach");

    await lib.setLanguage("hi");

    expect(has("hi", "coach")).toBe(true);
    expect(has("hi", "scam")).toBe(false);
    expect(lib.default.t("home.title", { ns: "coach" })).toBe("वित्तीय कोच");
  });

  it("load a namespace in the language already chosen", async () => {
    await lib.setLanguage("id");

    await lib.loadNamespace("scam");

    expect(has("id", "scam")).toBe(true);
    expect(lib.default.t("home.title", { ns: "scam" })).toBe("Cek penipuan");
  });

  it("fetch each file once, however often the language switches", async () => {
    const add = vi.spyOn(lib.default, "addResourceBundle");
    await lib.loadNamespace("coach");

    await lib.setLanguage("hi");
    await lib.setLanguage("en");
    await lib.setLanguage("hi");

    const added = add.mock.calls.map(([language, namespace]) => `${language}/${namespace}`);
    expect(added.filter((name) => name === "hi/coach")).toHaveLength(1);
    expect(added.filter((name) => name === "en/coach")).toHaveLength(1);
  });

  it("let a module's t() find shared strings without a prefix", async () => {
    await lib.loadNamespace("scam");

    expect(lib.default.t("common.loading", { ns: "scam" })).toBe("Loading…");
  });

  it("leave a module in English when its file in the new language cannot be fetched", async () => {
    await lib.loadNamespace("coach");

    await lib.setLanguage("tl");

    expect(lib.default.resolvedLanguage).toBe("tl");
    expect(has("tl", "coach")).toBe(false);
    expect(lib.default.t("home.title", { ns: "coach" })).toBe("Financial Coach");
  });

  it("do not stop the language switching for a module that was never opened", async () => {
    await lib.setLanguage("tl");

    expect(lib.default.resolvedLanguage).toBe("tl");
    expect(has("tl", "coach")).toBe(false);
  });
});
