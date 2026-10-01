import {
  type AppCheck,
  getToken,
  initializeAppCheck,
  ReCaptchaV3Provider,
} from "firebase/app-check";

import { firebaseApp } from "@/lib/firebase";

const SITE_KEY = import.meta.env.VITE_FIREBASE_APPCHECK_SITE_KEY;

/** Unset means the app sends no App Check token at all — the normal, fully-supported state
 * for anyone who hasn't configured Firebase App Check, matching the backend's own
 * `APP_CHECK_ENABLED` default of off (NF-P3-025). */
export const isAppCheckConfigured = Boolean(SITE_KEY);

let appCheck: AppCheck | null = null;

function appCheckInstance(): AppCheck | null {
  if (!isAppCheckConfigured) {
    return null;
  }
  appCheck ??= initializeAppCheck(firebaseApp, {
    provider: new ReCaptchaV3Provider(SITE_KEY as string),
    isTokenAutoRefreshEnabled: true,
  });
  return appCheck;
}

/**
 * The `X-Firebase-AppCheck` header for a request worth protecting, or `{}` when App Check
 * isn't configured here. Spread the result into a request's headers unconditionally — never
 * throws, so a token failure (or no configuration at all) degrades to "no header sent," the
 * same shape either way, not a broken request.
 */
export async function appCheckHeader(): Promise<Record<string, string>> {
  const instance = appCheckInstance();
  if (instance === null) {
    return {};
  }
  try {
    const { token } = await getToken(instance);
    return { "X-Firebase-AppCheck": token };
  } catch {
    return {};
  }
}
