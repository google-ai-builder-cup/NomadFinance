import { initializeApp } from "firebase/app";
import { connectAuthEmulator, getAuth } from "firebase/auth";
import { connectFirestoreEmulator, getFirestore } from "firebase/firestore";

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
});

export const auth = getAuth(firebaseApp);
export const db = getFirestore(firebaseApp);

// The emulator gives fake Google accounts and prints SMS codes instead of sending them,
// so sign-in can be tested without billing or real phones (see the NF-P1-009 runbook).
if (import.meta.env.VITE_USE_FIREBASE_EMULATOR === "true") {
  connectAuthEmulator(
    auth,
    import.meta.env.VITE_FIREBASE_AUTH_EMULATOR_URL ?? "http://127.0.0.1:9099"
  );
  // Port 8085, not Firestore's default 8080, which the backend uses (frontend/firebase.json).
  connectFirestoreEmulator(
    db,
    "127.0.0.1",
    Number(import.meta.env.VITE_FIRESTORE_EMULATOR_PORT ?? 8085)
  );
}
