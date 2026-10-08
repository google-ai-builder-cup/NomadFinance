// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { anonymisePath } from "@/lib/analytics";
import routerSource from "@/router.tsx?raw";

const sdk = vi.hoisted(() => ({
  isSupported: vi.fn(),
  initializeAnalytics: vi.fn(() => ({ name: "analytics" })),
  logEvent: vi.fn(),
  setUserProperties: vi.fn(),
}));

vi.mock("firebase/analytics", () => sdk);
vi.mock("@/lib/firebase", () => ({ firebaseApp: { name: "app" } }));

// The module reads its env once at import time, so each test loads a fresh copy.
async function loadModule(env: Record<string, string>) {
  vi.resetModules();
  vi.stubEnv("VITE_FIREBASE_MEASUREMENT_ID", env.VITE_FIREBASE_MEASUREMENT_ID ?? "");
  vi.stubEnv("VITE_USE_FIREBASE_EMULATOR", env.VITE_USE_FIREBASE_EMULATOR ?? "false");
  return import("@/lib/analytics");
}

// Events are sent from a promise chain; let it settle.
const settle = () => new Promise((resolve) => setTimeout(resolve, 0));

// Every event also carries the page's address, cleaned of ids, query and fragment.
const here = () => `${window.location.origin}${window.location.pathname}`;
const withLocation = (params: Record<string, unknown>) => ({ ...params, page_location: here() });

/** Opens `address` in the test page, as the browser would have it when an event fires. */
function openPage(address: string) {
  window.history.replaceState({}, "", address);
}

describe("analytics", () => {
  beforeEach(() => {
    sdk.isSupported.mockResolvedValue(true);
    openPage("/");
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
    openPage("/");
  });

  it("sends nothing and never loads the SDK without a measurement ID", async () => {
    const analytics = await loadModule({});
    analytics.trackPillarUsed("contract");
    await settle();
    expect(sdk.initializeAnalytics).not.toHaveBeenCalled();
    expect(sdk.logEvent).not.toHaveBeenCalled();
  });

  it("sends nothing against the emulator", async () => {
    const analytics = await loadModule({
      VITE_FIREBASE_MEASUREMENT_ID: "G-TEST",
      VITE_USE_FIREBASE_EMULATOR: "true",
    });
    analytics.trackLogin("google");
    await settle();
    expect(sdk.logEvent).not.toHaveBeenCalled();
  });

  it("sends nothing where the browser cannot run Analytics", async () => {
    sdk.isSupported.mockResolvedValue(false);
    const analytics = await loadModule({ VITE_FIREBASE_MEASUREMENT_ID: "G-TEST" });
    analytics.trackPillarUsed("radar");
    await settle();
    expect(sdk.initializeAnalytics).not.toHaveBeenCalled();
    expect(sdk.logEvent).not.toHaveBeenCalled();
  });

  it("initialises once and sends the custom events with only coarse parameters", async () => {
    const analytics = await loadModule({ VITE_FIREBASE_MEASUREMENT_ID: "G-TEST" });
    analytics.trackPillarUsed("remittance");
    analytics.trackContractAnalyzed("SG");
    analytics.trackRemittanceCompared("SG-PH");
    analytics.trackPageView("/dashboard");
    await settle();

    expect(sdk.initializeAnalytics).toHaveBeenCalledTimes(1);
    const sent = sdk.logEvent.mock.calls.map(([, name, params]) => [name, params]);
    expect(sent).toEqual([
      ["pillar_used", withLocation({ pillar_name: "remittance" })],
      ["contract_analyzed", withLocation({ host_country: "SG" })],
      ["remittance_compared", withLocation({ corridor_id: "SG-PH" })],
      ["page_view", withLocation({ page_path: "/dashboard" })],
    ]);
  });

  it("sets the four profile properties and clears them on sign-out", async () => {
    const analytics = await loadModule({ VITE_FIREBASE_MEASUREMENT_ID: "G-TEST" });
    analytics.setAnalyticsUserProperties({
      host_country: "SG",
      home_country: "PH",
      job_type: "care_worker",
      preferred_language: "tl",
    });
    analytics.clearAnalyticsUserProperties();
    await settle();

    expect(sdk.setUserProperties.mock.calls[0][1]).toEqual({
      host_country: "SG",
      home_country: "PH",
      job_type: "care_worker",
      preferred_language: "tl",
    });
    expect(sdk.setUserProperties.mock.calls[1][1]).toEqual({
      host_country: null,
      home_country: null,
      job_type: null,
      preferred_language: null,
    });
  });

  it("keeps the app running when the SDK fails to load", async () => {
    sdk.isSupported.mockRejectedValue(new Error("blocked"));
    const warn = vi.spyOn(console, "warn").mockImplementation(() => undefined);
    const analytics = await loadModule({ VITE_FIREBASE_MEASUREMENT_ID: "G-TEST" });
    expect(() => analytics.trackOnboardingCompleted()).not.toThrow();
    await settle();
    expect(warn).toHaveBeenCalled();
    warn.mockRestore();
  });

  describe("the Scam Analyzer events (NF-SA-022)", () => {
    async function configured() {
      return loadModule({ VITE_FIREBASE_MEASUREMENT_ID: "G-TEST" });
    }

    it("sends scam_check_submitted with the kind of input, the route and the language only", async () => {
      const analytics = await configured();

      analytics.trackScamCheckSubmitted("screenshot", "SG-IN", "hi");
      analytics.trackScamCheckSubmitted("text", undefined, "en");
      await settle();

      expect(sdk.logEvent).toHaveBeenNthCalledWith(
        1,
        expect.anything(),
        "scam_check_submitted",
        withLocation({ input_type: "screenshot", corridor_id: "SG-IN", ui_language: "hi" })
      );
      expect(sdk.logEvent).toHaveBeenNthCalledWith(
        2,
        expect.anything(),
        "scam_check_submitted",
        withLocation({ input_type: "text", corridor_id: "none", ui_language: "en" })
      );
    });

    it("names the language ui_language, because Google already owns a parameter called language", async () => {
      const analytics = await configured();

      analytics.trackScamCheckSubmitted("text", "SG-IN", "ne");
      await settle();

      const params = sdk.logEvent.mock.calls[0][2];
      expect(params).toHaveProperty("ui_language", "ne");
      expect(params).not.toHaveProperty("language");
    });

    it("sends scam_verdict_viewed with what the verdict said, never what it was about", async () => {
      const analytics = await configured();

      analytics.trackScamVerdictViewed({
        isScam: true,
        riskLevel: "high",
        scamType: "illegal_recruitment_fee",
        cached: false,
        source: "check",
      });
      analytics.trackScamVerdictViewed({
        isScam: false,
        riskLevel: "low",
        scamType: null,
        cached: true,
        source: "history",
      });
      await settle();

      expect(sdk.logEvent).toHaveBeenNthCalledWith(
        1,
        expect.anything(),
        "scam_verdict_viewed",
        withLocation({
          is_scam: true,
          risk_level: "high",
          scam_type: "illegal_recruitment_fee",
          cached: false,
          source: "check",
        })
      );
      expect(sdk.logEvent).toHaveBeenNthCalledWith(
        2,
        expect.anything(),
        "scam_verdict_viewed",
        withLocation({
          is_scam: false,
          risk_level: "low",
          scam_type: "none",
          cached: true,
          source: "history",
        })
      );
    });

    it("sends scam_reported with the kind of scam", async () => {
      const analytics = await configured();

      analytics.trackScamReported("lottery");
      await settle();

      expect(sdk.logEvent).toHaveBeenCalledWith(
        expect.anything(),
        "scam_reported",
        withLocation({ scam_type: "lottery" })
      );
    });

    it("sends none of them without a measurement ID", async () => {
      const analytics = await loadModule({});

      analytics.trackScamCheckSubmitted("text", "SG-IN", "en");
      analytics.trackScamReported("lottery");
      await settle();

      expect(sdk.logEvent).not.toHaveBeenCalled();
    });
  });

  describe("the address sent with every event", () => {
    const configured = () => loadModule({ VITE_FIREBASE_MEASUREMENT_ID: "G-TEST" });

    it.each([
      ["/contract/c_8f2a91d3", "/contract/:contractId"],
      ["/radar/entity/acme-recruitment-sg", "/radar/entity/:slug"],
      ["/scam-check/history/3f9a0c11d4e27b65", "/scam-check/history/:id"],
    ])("keeps the id out of %s", async (address, shape) => {
      openPage(`${address}?tab=2#top`);
      const analytics = await configured();

      analytics.trackScamReported("lottery");
      analytics.trackPageView(address);
      await settle();

      const [, , first] = sdk.logEvent.mock.calls[0];
      const [, , second] = sdk.logEvent.mock.calls[1];
      expect(first.page_location).toBe(`${window.location.origin}${shape}`);
      expect(second).toEqual({ page_path: shape, page_location: first.page_location });
      expect(JSON.stringify(sdk.logEvent.mock.calls)).not.toContain(address.split("/").pop());
    });

    it("drops the query and the fragment, so a message shared into the app is never sent", async () => {
      openPage(
        "/scam-check?title=Hi&text=Send+800+SGD+to+9123+4567&url=https%3A%2F%2Fevil.example#x"
      );
      const analytics = await configured();

      analytics.trackScamCheckSubmitted("text", undefined, "en");
      await settle();

      const sent = JSON.stringify(sdk.logEvent.mock.calls);
      expect(sdk.logEvent.mock.calls[0][2].page_location).toBe(
        `${window.location.origin}/scam-check`
      );
      expect(sent).not.toMatch(/9123|evil|800|Send/);
    });

    it("gives the events Google sends by itself the same clean address", async () => {
      openPage("/scam-check/history/3f9a0c11d4e27b65?text=secret");
      const analytics = await configured();

      analytics.trackLogin("google");
      await settle();

      expect(sdk.initializeAnalytics).toHaveBeenCalledWith(expect.anything(), {
        config: {
          send_page_view: false,
          debug_mode: expect.any(Boolean),
          page_location: `${window.location.origin}/scam-check/history/:id`,
        },
      });
    });

    it("cleans the page before this one when it is one of ours, and leaves outside pages alone", async () => {
      const referrer = vi.spyOn(document, "referrer", "get");
      const analytics = await configured();

      referrer.mockReturnValue(`${window.location.origin}/scam-check/history/3f9a0c11d4e27b65?q=1`);
      analytics.trackLogin("google");
      referrer.mockReturnValue("https://search.example/results?q=remit");
      analytics.trackLogin("phone");
      referrer.mockReturnValue("");
      analytics.trackLogin("phone");
      referrer.mockReturnValue("not a url");
      analytics.trackLogin("phone");
      await settle();
      referrer.mockRestore();

      const sent = sdk.logEvent.mock.calls.map(([, , params]) => params.page_referrer);
      expect(sent).toEqual([
        `${window.location.origin}/scam-check/history/:id`,
        undefined,
        undefined,
        undefined,
      ]);
    });

    it("keeps the id out of a crash report too", async () => {
      const analytics = await configured();

      analytics.trackCrash(new TypeError("boom"), "/contract/c_8f2a91d3");
      await settle();

      expect(sdk.logEvent.mock.calls[0][2].description).toBe("TypeError at /contract/:contractId");
    });

    it("reads the address when the event happens, not when the SDK is ready", async () => {
      const analytics = await configured();
      openPage("/scam-check/history/3f9a0c11d4e27b65");

      analytics.trackScamReported("lottery");
      openPage("/dashboard");
      await settle();

      expect(sdk.logEvent.mock.calls[0][2].page_location).toBe(
        `${window.location.origin}/scam-check/history/:id`
      );
    });
  });

  describe("anonymisePath", () => {
    it.each([
      "/",
      "/dashboard",
      "/contract",
      "/contract/history",
      "/contract/history/",
      "/radar/heatmap",
      "/radar/report",
      "/radar/alerts",
      "/scam-check",
      "/scam-check/history",
      "/identity/log",
      "/no-such-page",
    ])("leaves %s as it is", (path) => {
      expect(anonymisePath(path)).toBe(path);
    });

    it.each([
      ["/contract/abc", "/contract/:contractId"],
      ["/contract/abc/extra", "/contract/:contractId"],
      ["/contract/historyx", "/contract/:contractId"],
      ["/radar/entity/some-slug", "/radar/entity/:slug"],
      ["/scam-check/history/abc%20def", "/scam-check/history/:id"],
    ])("turns %s into %s", (path, shape) => {
      expect(anonymisePath(path)).toBe(shape);
    });

    it("covers every route of the app that has a :parameter", () => {
      const dynamic = [...routerSource.matchAll(/path:\s*"([^"]*:[A-Za-z]+[^"]*)"/g)].map(
        (match) => match[1]
      );

      // The pattern must still find the routes it is meant to guard.
      expect(dynamic.length).toBeGreaterThanOrEqual(3);
      for (const path of dynamic) {
        const probe = path.replace(/:[A-Za-z]+/g, "zq9x7k2m4p");
        expect(anonymisePath(probe), `${path} would reach Analytics with its id`).not.toContain(
          "zq9x7k2m4p"
        );
      }
    });
  });

  describe("what the events carry", () => {
    // Event parameters Google adds to every web event itself, and names it reserves:
    // https://support.google.com/firebase/answer/6317485
    // https://support.google.com/analytics/answer/13316687
    const ADDED_BY_GOOGLE = [
      "language",
      "page_location",
      "page_referrer",
      "page_title",
      "screen_resolution",
    ];
    const RESERVED = [
      ...["cid", "currency", "customer_id", "customerid", "dclid", "gclid", "session_id"],
      ...["sessionid", "sfmc_id", "sid", "srsltid", "uid", "user_id", "userid"],
    ];
    const RESERVED_PREFIXES = ["_", "firebase_", "ga_", "google_", "gtag."];
    // Sent on purpose by track(), cleaned of ids: see "the address sent with every event".
    const SENT_ON_PURPOSE = ["page_location", "page_referrer"];

    function problemWith(name: string): string | null {
      if (SENT_ON_PURPOSE.includes(name)) {
        return null;
      }
      if (ADDED_BY_GOOGLE.includes(name)) {
        return `${name} is added by Google to every event; a custom one is lost`;
      }
      if (RESERVED.includes(name) || RESERVED_PREFIXES.some((prefix) => name.startsWith(prefix))) {
        return `${name} is reserved by Google`;
      }
      return null;
    }

    async function sendOneOfEverything() {
      const analytics = await loadModule({ VITE_FIREBASE_MEASUREMENT_ID: "G-TEST" });
      analytics.trackPageView("/dashboard");
      analytics.trackPillarUsed("identity");
      analytics.trackContractAnalyzed("AU");
      analytics.trackRemittanceCompared("AU-PH");
      analytics.trackScamCheckSubmitted("screenshot", "SG-PH", "tl");
      analytics.trackScamVerdictViewed({
        isScam: true,
        riskLevel: "medium",
        scamType: "loan_app_trap",
        cached: true,
        source: "history",
      });
      analytics.trackScamReported("lottery");
      analytics.trackLogin("phone");
      analytics.trackOnboardingCompleted();
      analytics.trackCrash(new RangeError("x"), "/dashboard");
      await settle();
      return sdk.logEvent.mock.calls.map(([, name, params]) => ({
        name: name as string,
        params: (params ?? {}) as Record<string, unknown>,
      }));
    }

    it("would have caught the name that went wrong", () => {
      expect(problemWith("language")).not.toBeNull();
      expect(problemWith("user_id")).not.toBeNull();
      expect(problemWith("google_thing")).not.toBeNull();
      expect(problemWith("ui_language")).toBeNull();
    });

    it("uses no parameter name that Google adds itself or reserves", async () => {
      const sent = await sendOneOfEverything();

      expect(sent.length).toBe(10);
      for (const { name, params } of sent) {
        for (const parameter of Object.keys(params)) {
          expect(problemWith(parameter), `${name}: ${parameter}`).toBeNull();
        }
      }
    });

    it("sends short ids and flags, never free text, apart from the address and a crash", async () => {
      const sent = await sendOneOfEverything();

      for (const { name, params } of sent) {
        if (name === "exception") {
          continue;
        }
        for (const [parameter, value] of Object.entries(params)) {
          if (SENT_ON_PURPOSE.includes(parameter)) {
            continue;
          }
          expect(String(value), `${name}: ${parameter}`).toMatch(/^[A-Za-z0-9_/:-]{1,40}$/);
        }
      }
    });
  });
});
