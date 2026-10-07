import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

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

describe("analytics", () => {
  beforeEach(() => {
    sdk.isSupported.mockResolvedValue(true);
  });

  afterEach(() => {
    vi.unstubAllEnvs();
    vi.clearAllMocks();
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
      ["pillar_used", { pillar_name: "remittance" }],
      ["contract_analyzed", { host_country: "SG" }],
      ["remittance_compared", { corridor_id: "SG-PH" }],
      ["page_view", { page_path: "/dashboard" }],
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

      expect(sdk.logEvent).toHaveBeenNthCalledWith(1, expect.anything(), "scam_check_submitted", {
        input_type: "screenshot",
        corridor_id: "SG-IN",
        language: "hi",
      });
      expect(sdk.logEvent).toHaveBeenNthCalledWith(2, expect.anything(), "scam_check_submitted", {
        input_type: "text",
        corridor_id: "none",
        language: "en",
      });
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

      expect(sdk.logEvent).toHaveBeenNthCalledWith(1, expect.anything(), "scam_verdict_viewed", {
        is_scam: true,
        risk_level: "high",
        scam_type: "illegal_recruitment_fee",
        cached: false,
        source: "check",
      });
      expect(sdk.logEvent).toHaveBeenNthCalledWith(2, expect.anything(), "scam_verdict_viewed", {
        is_scam: false,
        risk_level: "low",
        scam_type: "none",
        cached: true,
        source: "history",
      });
    });

    it("sends scam_reported with the kind of scam", async () => {
      const analytics = await configured();

      analytics.trackScamReported("lottery");
      await settle();

      expect(sdk.logEvent).toHaveBeenCalledWith(expect.anything(), "scam_reported", {
        scam_type: "lottery",
      });
    });

    it("sends none of them without a measurement ID", async () => {
      const analytics = await loadModule({});

      analytics.trackScamCheckSubmitted("text", "SG-IN", "en");
      analytics.trackScamReported("lottery");
      await settle();

      expect(sdk.logEvent).not.toHaveBeenCalled();
    });
  });
});
