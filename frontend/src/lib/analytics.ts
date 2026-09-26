import type { Analytics } from "firebase/analytics";

import { firebaseApp } from "@/lib/firebase";
import type { HomeCountry, HostCountry, JobType, LanguageCode } from "@/types/enums";

export type PillarId = "remittance" | "contract" | "radar" | "identity";

export interface AnalyticsUserProperties {
  host_country: HostCountry;
  home_country: HomeCountry;
  job_type: JobType;
  preferred_language: LanguageCode;
}

type FirebaseAnalyticsModule = typeof import("firebase/analytics");

interface Ready {
  analytics: Analytics;
  sdk: FirebaseAnalyticsModule;
}

// No measurement ID means analytics is simply off. The emulator flag keeps test sessions out too.
const enabled =
  Boolean(import.meta.env.VITE_FIREBASE_MEASUREMENT_ID) &&
  import.meta.env.VITE_USE_FIREBASE_EMULATOR !== "true";

let ready: Promise<Ready | null> | null = null;

// Loaded on first use so the SDK stays out of the main bundle, and isSupported() rules out
// browsers where it cannot run (private modes, blocked storage, in-app browsers).
function load(): Promise<Ready | null> {
  if (!enabled) {
    return Promise.resolve(null);
  }
  ready ??= import("firebase/analytics")
    .then(async (sdk) => {
      if (!(await sdk.isSupported())) {
        return null;
      }
      const analytics = sdk.initializeAnalytics(firebaseApp, {
        // Page views are sent by hand on route changes; the automatic one only sees full loads.
        config: { send_page_view: false, debug_mode: import.meta.env.DEV },
      });
      return { analytics, sdk };
    })
    // Measuring usage must never break the app it measures.
    .catch((error: unknown) => {
      console.warn("Analytics unavailable:", error);
      return null;
    });
  return ready;
}

function run(action: (target: Ready) => void): void {
  void load().then((target) => {
    if (target !== null) {
      action(target);
    }
  });
}

function track(name: string, params?: Record<string, string | boolean>): void {
  run(({ analytics, sdk }) => sdk.logEvent(analytics, name, params));
}

/** Pathname only: query strings and fragments could carry personal data. */
export function trackPageView(pathname: string): void {
  track("page_view", { page_path: pathname });
}

/** A person opened one of the four pillars. */
export function trackPillarUsed(pillar: PillarId): void {
  track("pillar_used", { pillar_name: pillar });
}

/** A contract finished analysis. Called by the Contract Shield flow once it exists. */
export function trackContractAnalyzed(hostCountry: HostCountry): void {
  track("contract_analyzed", { host_country: hostCountry });
}

export function trackLogin(method: "google" | "phone"): void {
  track("login", { method });
}

export function trackOnboardingCompleted(): void {
  track("onboarding_completed");
}

/**
 * A page crashed and the error screen was shown. Only the error type and the path are sent:
 * error messages can quote what the person typed or was shown.
 */
export function trackCrash(error: unknown, pathname: string): void {
  const kind = error instanceof Error ? error.name : typeof error;
  track("exception", { description: `${kind} at ${pathname}`, fatal: true });
}

/** Coarse profile facts only: no name, phone, email or uid ever goes to Analytics. */
export function setAnalyticsUserProperties(properties: AnalyticsUserProperties): void {
  run(({ analytics, sdk }) => sdk.setUserProperties(analytics, { ...properties }));
}

// Phones are shared, so the last person's profile must not stick to the next one's events.
export function clearAnalyticsUserProperties(): void {
  run(({ analytics, sdk }) =>
    sdk.setUserProperties(analytics, {
      host_country: null,
      home_country: null,
      job_type: null,
      preferred_language: null,
    })
  );
}
