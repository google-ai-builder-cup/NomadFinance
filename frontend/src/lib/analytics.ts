import type { Analytics } from "firebase/analytics";

import { firebaseApp } from "@/lib/firebase";
import type { CorridorId, HomeCountry, HostCountry, JobType, LanguageCode } from "@/types/enums";

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

// Pages whose address ends in something that names one record: a contract, a Radar entity, a
// stored scam check. Analytics gets the shape of the route, never the id or the slug in it.
// A new route with a `:param` must be listed here; analytics.test.ts fails until it is.
const IDENTIFYING_ROUTES: ReadonlyArray<readonly [RegExp, string]> = [
  [/^\/contract\/(?!history\/?$)[^/].*$/, "/contract/:contractId"],
  [/^\/radar\/entity\/[^/].*$/, "/radar/entity/:slug"],
  [/^\/scam-check\/history\/[^/].*$/, "/scam-check/history/:id"],
];

/** The route a pathname belongs to, without the ids in it: all Analytics may keep of a path. */
export function anonymisePath(pathname: string): string {
  const route = IDENTIFYING_ROUTES.find(([pattern]) => pattern.test(pathname));
  return route ? route[1] : pathname;
}

// Google adds `page_location` (the full address) to every event, and the address can hold what
// the app promises not to send: the id of a stored check, and, for a message shared into the
// app, the message itself (`/scam-check?text=...`). So the address is always sent by hand,
// with no query, no fragment and no id.
function safeLocation(): string {
  return `${window.location.origin}${anonymisePath(window.location.pathname)}`;
}

// The page before this one is the same kind of address when it is one of ours; an outside page
// is left to Google, it is not the worker's data.
function safeReferrer(): string | undefined {
  if (document.referrer === "") {
    return undefined;
  }
  try {
    const referrer = new URL(document.referrer);
    return referrer.origin === window.location.origin
      ? `${referrer.origin}${anonymisePath(referrer.pathname)}`
      : undefined;
  } catch {
    return undefined;
  }
}

// Loaded on first use so the SDK stays out of the main bundle, and isSupported() rules out
// browsers where it cannot run (private modes, blocked storage, in-app browsers).
function load(): Promise<Ready | null> {
  if (!enabled) {
    return Promise.resolve(null);
  }
  const firstLocation = safeLocation();
  ready ??= import("firebase/analytics")
    .then(async (sdk) => {
      if (!(await sdk.isSupported())) {
        return null;
      }
      const analytics = sdk.initializeAnalytics(firebaseApp, {
        // Page views are sent by hand on route changes; the automatic one only sees full loads.
        // `page_location` here is for the events Google sends by itself (session_start,
        // first_visit), which would otherwise carry the raw address of the first page.
        config: {
          send_page_view: false,
          debug_mode: import.meta.env.DEV,
          page_location: firstLocation,
        },
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
  // Read now, not when the SDK is ready: the worker may have moved on by then.
  const pageLocation = safeLocation();
  const pageReferrer = safeReferrer();
  run(({ analytics, sdk }) =>
    sdk.logEvent(analytics, name, {
      ...params,
      page_location: pageLocation,
      ...(pageReferrer === undefined ? {} : { page_referrer: pageReferrer }),
    })
  );
}

/** The route only: no query string or fragment, and no id (see `anonymisePath`). */
export function trackPageView(pathname: string): void {
  track("page_view", { page_path: anonymisePath(pathname) });
}

/** A person opened one of the four pillars. */
export function trackPillarUsed(pillar: PillarId): void {
  track("pillar_used", { pillar_name: pillar });
}

/** A contract finished analysis. Called by the Contract Shield flow once it exists. */
export function trackContractAnalyzed(hostCountry: HostCountry): void {
  track("contract_analyzed", { host_country: hostCountry });
}

/** A remittance comparison was shown. The corridor only: the amount is the person's own. */
export function trackRemittanceCompared(corridorId: CorridorId): void {
  track("remittance_compared", { corridor_id: corridorId });
}

/**
 * A worker sent a message or a screenshot to the Scam Analyzer (NF-SA-022). What kind of input,
 * the route they are on, and the language: never the message, its words, or anything in it.
 *
 * The parameter is `ui_language`, not `language`: Google already attaches a `language` (the
 * browser's) to every web event, and a custom parameter of that name never reached the report.
 */
export function trackScamCheckSubmitted(
  inputType: "text" | "screenshot",
  corridorId: CorridorId | undefined,
  language: LanguageCode
): void {
  track("scam_check_submitted", {
    input_type: inputType,
    corridor_id: corridorId ?? "none",
    ui_language: language,
  });
}

export interface ScamVerdictViewed {
  isScam: boolean;
  riskLevel: "low" | "medium" | "high";
  /** A taxonomy id such as "lottery"; null for a message that is not a scam. */
  scamType: string | null;
  /** The answer came from an earlier check of the same message. */
  cached: boolean;
  /** A check that has just finished, or a stored one opened from the history. */
  source: "check" | "history";
}

/** A verdict was put in front of a worker (NF-SA-022): what it said, not what it was about. */
export function trackScamVerdictViewed(view: ScamVerdictViewed): void {
  track("scam_verdict_viewed", {
    is_scam: view.isScam,
    risk_level: view.riskLevel,
    scam_type: view.scamType ?? "none",
    cached: view.cached,
    source: view.source,
  });
}

/** A worker warned others about a scam, through "Warn other workers" (NF-SA-022). The kind only. */
export function trackScamReported(scamType: string): void {
  track("scam_reported", { scam_type: scamType });
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
  track("exception", { description: `${kind} at ${anonymisePath(pathname)}`, fatal: true });
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
