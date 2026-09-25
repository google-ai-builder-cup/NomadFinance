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
    analytics.trackPageView("/dashboard");
    await settle();

    expect(sdk.initializeAnalytics).toHaveBeenCalledTimes(1);
    const sent = sdk.logEvent.mock.calls.map(([, name, params]) => [name, params]);
    expect(sent).toEqual([
      ["pillar_used", { pillar_name: "remittance" }],
      ["contract_analyzed", { host_country: "SG" }],
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
});
