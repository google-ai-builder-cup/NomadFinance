import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import path from "node:path";

import type { Page } from "@playwright/test";

// The browser tests sign in through the Firebase emulators (`firebase emulators:exec --only
// auth,firestore --project demo-nomadfinance`), against a build made with `--mode emulator`.
// Nothing here reaches real Firebase: the project is `demo-` and the ports are local.
export const AUTH_URL = "http://127.0.0.1:9099";
export const FIRESTORE_URL = "http://127.0.0.1:8085";
export const PROJECT_ID = "demo-nomadfinance";

/** The API key the build was made with (.env.emulator); the emulator accepts any, but the saved
 * sign-in is stored under it, so the browser only finds it when they match. */
function buildApiKey(): string {
  const env = readFileSync(path.resolve(process.cwd(), ".env.emulator"), "utf8");
  const match = /^VITE_FIREBASE_API_KEY=(.+)$/m.exec(env);
  if (!match) {
    throw new Error("VITE_FIREBASE_API_KEY is missing from frontend/.env.emulator");
  }
  return match[1].trim();
}

export interface TestUser {
  uid: string;
  email: string;
  idToken: string;
  refreshToken: string;
  expiresInSeconds: number;
}

/** A new account in the Auth emulator. Each call is a different person, so tests never share one. */
export async function createUser(): Promise<TestUser> {
  // A random id: the desktop and phone projects run in separate processes at the same moment.
  const email = `worker-${randomUUID()}@e2e.example`;
  const response = await fetch(
    `${AUTH_URL}/identitytoolkit.googleapis.com/v1/accounts:signUp?key=${buildApiKey()}`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email, password: "e2e-only-password", returnSecureToken: true }),
    }
  );
  if (!response.ok) {
    throw new Error(
      `The Auth emulator refused the new account (${response.status}). Is it running?`
    );
  }
  const body = (await response.json()) as {
    localId: string;
    idToken: string;
    refreshToken: string;
    expiresIn: string;
  };
  return {
    uid: body.localId,
    email,
    idToken: body.idToken,
    refreshToken: body.refreshToken,
    expiresInSeconds: Number(body.expiresIn),
  };
}

/**
 * The profile a worker has once onboarding is done: without it the app sends them to
 * /onboarding. Written with the emulator's admin token, which skips the security rules.
 */
export async function seedProfile(uid: string): Promise<void> {
  const now = new Date().toISOString();
  const response = await fetch(
    `${FIRESTORE_URL}/v1/projects/${PROJECT_ID}/databases/(default)/documents/users/${uid}`,
    {
      method: "PATCH",
      headers: { "Content-Type": "application/json", Authorization: "Bearer owner" },
      body: JSON.stringify({
        fields: {
          preferred_language: { stringValue: "en" },
          host_country: { stringValue: "SG" },
          home_country: { stringValue: "IN" },
          job_type: { stringValue: "care_worker" },
          onboarding_completed_at: { timestampValue: now },
          created_at: { timestampValue: now },
          updated_at: { timestampValue: now },
          schema_version: { integerValue: "1" },
        },
      }),
    }
  );
  if (!response.ok) {
    throw new Error(
      `The Firestore emulator refused the profile (${response.status}). Is it running?`
    );
  }
}

/**
 * Signs the browser in the way Firebase remembers a returning visitor: the user is saved in
 * IndexedDB, and on the next load the SDK restores it and checks it with the emulator. This is
 * the same state a real sign-in leaves, without driving the Google or phone screens, which the
 * emulator cannot make reliable in CI.
 */
export async function signIn(page: Page, user: TestUser): Promise<void> {
  const apiKey = buildApiKey();
  // Any page of the app's own origin: IndexedDB belongs to the origin.
  await page.goto("/robots.txt");
  await page.evaluate(
    async ({ apiKey, user }) => {
      const now = Date.now();
      const record = {
        fbase_key: `firebase:authUser:${apiKey}:[DEFAULT]`,
        value: {
          uid: user.uid,
          email: user.email,
          emailVerified: false,
          isAnonymous: false,
          providerData: [
            {
              providerId: "password",
              uid: user.email,
              email: user.email,
              displayName: null,
              phoneNumber: null,
              photoURL: null,
            },
          ],
          stsTokenManager: {
            refreshToken: user.refreshToken,
            accessToken: user.idToken,
            expirationTime: now + user.expiresInSeconds * 1000,
          },
          createdAt: String(now),
          lastLoginAt: String(now),
          apiKey,
          appName: "[DEFAULT]",
        },
      };
      await new Promise<void>((resolve, reject) => {
        const open = indexedDB.open("firebaseLocalStorageDb", 1);
        open.onupgradeneeded = () => {
          open.result.createObjectStore("firebaseLocalStorage", { keyPath: "fbase_key" });
        };
        open.onerror = () => reject(open.error);
        open.onsuccess = () => {
          const db = open.result;
          const tx = db.transaction("firebaseLocalStorage", "readwrite");
          tx.objectStore("firebaseLocalStorage").put(record);
          tx.oncomplete = () => {
            db.close();
            resolve();
          };
          tx.onerror = () => reject(tx.error);
        };
      });
    },
    { apiKey, user }
  );
}

/** A new worker, already onboarded and signed in on this page. */
export async function signedInWorker(page: Page): Promise<TestUser> {
  // The emulator build pins a warning banner to the bottom of the screen, which on a phone
  // covers the buttons a test needs to press. A production build has no such banner.
  await page.addInitScript(() => {
    document.addEventListener("DOMContentLoaded", () => {
      const style = document.createElement("style");
      style.textContent = ".firebase-emulator-warning { display: none !important; }";
      document.head.appendChild(style);
    });
  });
  const user = await createUser();
  await seedProfile(user.uid);
  await signIn(page, user);
  return user;
}
