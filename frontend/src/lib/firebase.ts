import { initializeApp } from "firebase/app";
import {
  browserLocalPersistence,
  browserSessionPersistence,
  connectAuthEmulator,
  indexedDBLocalPersistence,
  initializeAuth,
} from "firebase/auth";

type FirebaseEnvKey =
  | "VITE_FIREBASE_API_KEY"
  | "VITE_FIREBASE_AUTH_DOMAIN"
  | "VITE_FIREBASE_PROJECT_ID"
  | "VITE_FIREBASE_APP_ID";

// Fail at startup with a clear message instead of a vague Firebase error on first sign-in.
function requireEnv(name: FirebaseEnvKey): string {
  const value = import.meta.env[name];
  if (!value) {
    throw new Error(`Missing ${name}. Copy frontend/.env.example to .env.local and fill it in.`);
  }
  return value;
}

export const firebaseApp = initializeApp({
  apiKey: requireEnv("VITE_FIREBASE_API_KEY"),
  authDomain: requireEnv("VITE_FIREBASE_AUTH_DOMAIN"),
  projectId: requireEnv("VITE_FIREBASE_PROJECT_ID"),
  appId: requireEnv("VITE_FIREBASE_APP_ID"),
  // Optional: without it Analytics stays off (lib/analytics.ts) and nothing else changes.
  measurementId: import.meta.env.VITE_FIREBASE_MEASUREMENT_ID || undefined,
  // Optional: without it push notifications stay off (lib/messaging.ts) and nothing else
  // changes — every other Firebase feature works with this unset.
  messagingSenderId: import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID || undefined,
});

// initializeAuth without a popup/redirect resolver, unlike getAuth: with one, Firebase loads
// Google's apis.google.com scripts at start-up and does not say whether anyone is signed in
// until they arrive, which on a slow connection is several seconds of every page. The
// resolver is passed to the three calls that need it instead (services/authService.ts).
// Persistence is getAuth's default order (NF-P4-003).
export const auth = initializeAuth(firebaseApp, {
  persistence: [indexedDBLocalPersistence, browserLocalPersistence, browserSessionPersistence],
});

// The emulator gives fake Google accounts and prints SMS codes instead of sending them,
// so sign-in can be tested without billing or real phones (see the NF-P1-009 runbook).
if (import.meta.env.VITE_USE_FIREBASE_EMULATOR === "true") {
  connectAuthEmulator(
    auth,
    import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_URL ?? "http://127.0.0.1:9099"
  );
}
