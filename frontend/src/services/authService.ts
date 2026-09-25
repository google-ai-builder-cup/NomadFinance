import { FirebaseError } from "firebase/app";
import {
  type ConfirmationResult,
  getRedirectResult,
  GoogleAuthProvider,
  reauthenticateWithPhoneNumber,
  reauthenticateWithPopup,
  RecaptchaVerifier,
  signOut as firebaseSignOut,
  signInWithPhoneNumber,
  signInWithPopup,
  signInWithRedirect,
} from "firebase/auth";

import { auth } from "@/lib/firebase";

const googleProvider = new GoogleAuthProvider();
// Shared phones are common among workers; always let them pick the account.
googleProvider.setCustomParameters({ prompt: "select_account" });

export async function signInWithGoogle(): Promise<void> {
  try {
    await signInWithPopup(auth, googleProvider);
  } catch (error) {
    // In-app browsers (Facebook, WhatsApp links) block popups; a full-page redirect still works.
    // The redirect result arrives through onAuthStateChanged in AuthProvider.
    if (error instanceof FirebaseError && error.code === "auth/popup-blocked") {
      await signInWithRedirect(auth, googleProvider);
      return;
    }
    throw error;
  }
}

/**
 * Error from a Google redirect sign-in, as an i18n key. Success needs no handling here:
 * it arrives through onAuthStateChanged, but a failure is only reported by this call.
 */
export async function redirectSignInErrorKey(): Promise<string | null> {
  try {
    await getRedirectResult(auth);
    return null;
  } catch (error) {
    return authErrorKey(error);
  }
}

/**
 * Invisible reCAPTCHA required by Firebase phone auth. Pass a fresh, attached element for
 * each attempt: a cleared verifier can't be rendered into the same element again.
 */
export function createRecaptchaVerifier(container: HTMLElement): RecaptchaVerifier {
  return new RecaptchaVerifier(auth, container, { size: "invisible" });
}

export function disposeRecaptchaVerifier(verifier: RecaptchaVerifier): void {
  try {
    verifier.clear();
  } catch (error) {
    // Firebase destroys the verifier itself after some failed attempts; clearing it again
    // throws auth/internal-error, which is harmless here.
    if (!(error instanceof FirebaseError && error.code === "auth/internal-error")) {
      throw error;
    }
  }
}

export function sendPhoneCode(
  phoneNumberE164: string,
  verifier: RecaptchaVerifier
): Promise<ConfirmationResult> {
  return signInWithPhoneNumber(auth, phoneNumberE164, verifier);
}

export async function confirmPhoneCode(
  confirmation: ConfirmationResult,
  code: string
): Promise<void> {
  await confirmation.confirm(code);
}

export function signOut(): Promise<void> {
  return firebaseSignOut(auth);
}

export type SignInMethod = "google" | "phone" | "other";

/** How the current user signs in, which decides how they can confirm it is really them. */
export function signInMethod(): SignInMethod {
  const providers = auth.currentUser?.providerData.map((info) => info.providerId) ?? [];
  if (providers.includes("google.com")) {
    return "google";
  }
  return providers.includes("phone") ? "phone" : "other";
}

/** True when the user signed in (not just refreshed a token) within the last `seconds`. */
export async function signedInWithin(seconds: number): Promise<boolean> {
  const result = await auth.currentUser?.getIdTokenResult();
  return result !== undefined && Date.now() - Date.parse(result.authTime) <= seconds * 1000;
}

/** Confirm identity with Google again. Afterwards the token carries a fresh sign-in time. */
export async function reauthenticateWithGoogle(): Promise<void> {
  const user = auth.currentUser;
  if (user === null) {
    throw new Error("Not signed in");
  }
  await reauthenticateWithPopup(user, googleProvider);
  await user.getIdToken(true);
}

/** Text a new code to the phone number this account already uses. */
export function sendReauthCode(verifier: RecaptchaVerifier): Promise<ConfirmationResult> {
  const user = auth.currentUser;
  if (user?.phoneNumber == null) {
    throw new Error("This account has no phone number");
  }
  return reauthenticateWithPhoneNumber(user, user.phoneNumber, verifier);
}

export async function confirmReauthCode(
  confirmation: ConfirmationResult,
  code: string
): Promise<void> {
  await confirmation.confirm(code);
  await auth.currentUser?.getIdToken(true);
}

/** ID token for `Authorization: Bearer` on backend calls; Firebase refreshes it when needed. */
export async function getIdToken(): Promise<string | null> {
  return (await auth.currentUser?.getIdToken()) ?? null;
}

/**
 * Map a sign-in failure to an i18n key, or null when the user simply cancelled.
 * Firebase error codes: https://firebase.google.com/docs/reference/js/auth#autherrorcodes
 */
export function authErrorKey(error: unknown): string | null {
  const code = error instanceof FirebaseError ? error.code : "";
  switch (code) {
    case "auth/popup-closed-by-user":
    case "auth/cancelled-popup-request":
    case "auth/user-cancelled":
      return null;
    case "auth/invalid-phone-number":
    case "auth/missing-phone-number":
      return "auth.error.invalidPhone";
    case "auth/invalid-verification-code":
    case "auth/missing-verification-code":
      return "auth.error.invalidCode";
    case "auth/code-expired":
      return "auth.error.codeExpired";
    case "auth/too-many-requests":
    case "auth/quota-exceeded":
      return "auth.error.tooManyRequests";
    case "auth/network-request-failed":
      return "auth.error.network";
    // reCAPTCHA token rejected. Always the case for real numbers on localhost, which
    // Firebase doesn't accept as a domain for phone auth; test numbers skip the check.
    case "auth/invalid-app-credential":
    case "auth/captcha-check-failed":
      return "auth.error.securityCheck";
    case "auth/operation-not-allowed":
    case "auth/billing-not-enabled":
    case "auth/unauthorized-domain":
      return "auth.error.unavailable";
    case "auth/account-exists-with-different-credential":
      return "auth.error.accountExists";
    default:
      return "auth.error.generic";
  }
}
