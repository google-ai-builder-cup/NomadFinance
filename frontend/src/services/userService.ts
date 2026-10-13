import {
  arrayRemove,
  arrayUnion,
  doc,
  getDoc,
  serverTimestamp,
  setDoc,
  updateDoc,
} from "firebase/firestore";

import { db } from "@/lib/firestore";
import type { OnboardingAnswers, ProfileChanges, UserProfile } from "@/types/user";

function profileRef(uid: string) {
  return doc(db, "users", uid);
}

export async function getUserProfile(uid: string): Promise<UserProfile | null> {
  const snapshot = await getDoc(profileRef(uid));
  return snapshot.exists() ? (snapshot.data() as UserProfile) : null;
}

export function isOnboarded(profile: UserProfile | null | undefined): boolean {
  return profile?.onboarding_completed_at !== undefined;
}

/**
 * Save the onboarding answers. The Firestore rules (NF-P1-014) only accept
 * serverTimestamp() for the timestamps and schema_version 1 on create, and on update
 * they refuse any change to created_at or schema_version, hence two write shapes.
 */
export async function completeOnboarding(
  uid: string,
  answers: OnboardingAnswers,
  profileExists: boolean
): Promise<void> {
  const fields = {
    ...answers,
    onboarding_completed_at: serverTimestamp(),
    updated_at: serverTimestamp(),
  };
  if (profileExists) {
    await updateDoc(profileRef(uid), fields);
  } else {
    await setDoc(profileRef(uid), { ...fields, created_at: serverTimestamp(), schema_version: 1 });
  }
}

/**
 * Save edits from the profile page straight to `users/{uid}`. The rules accept only the
 * profile fields plus a server `updated_at`, so anything else is refused, not stored.
 */
export async function updateProfile(uid: string, changes: ProfileChanges): Promise<void> {
  await updateDoc(profileRef(uid), { ...changes, updated_at: serverTimestamp() });
}

/**
 * Add one push token to `fcm_tokens` (NF-P3-009). `arrayUnion`, not a plain field write: a
 * person may have several browsers/devices, and the rules cap the list at 5 (NF-P1-014) —
 * the backend trims a token off when FCM reports it gone, this only ever adds one.
 */
export async function saveFcmToken(uid: string, token: string): Promise<void> {
  await updateDoc(profileRef(uid), {
    fcm_tokens: arrayUnion(token),
    updated_at: serverTimestamp(),
  });
}

/** Take one push token off `fcm_tokens`, when this browser stops receiving the worker's pushes. */
export async function removeFcmToken(uid: string, token: string): Promise<void> {
  await updateDoc(profileRef(uid), {
    fcm_tokens: arrayRemove(token),
    updated_at: serverTimestamp(),
  });
}
