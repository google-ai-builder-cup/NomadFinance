import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/hooks/useAuth";
import { completeOnboarding, getUserProfile, updateProfile } from "@/services/userService";
import type { OnboardingAnswers, ProfileChanges } from "@/types/user";

function profileKey(uid: string | undefined) {
  return ["userProfile", uid] as const;
}

/** The signed-in user's Firestore profile; `data` is null until onboarding creates it. */
export function useUserProfile() {
  const { user } = useAuth();
  const uid = user?.uid;
  return useQuery({
    queryKey: profileKey(uid),
    queryFn: () => getUserProfile(uid ?? ""),
    enabled: uid !== undefined,
    // Only this app writes the profile, and every write refreshes the cache itself.
    staleTime: Infinity,
  });
}

export function useCompleteOnboarding() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const profile = useUserProfile();
  const uid = user?.uid ?? "";

  return useMutation({
    mutationFn: (answers: OnboardingAnswers) =>
      completeOnboarding(uid, answers, profile.data !== null && profile.data !== undefined),
    // The onboarding page shows the error next to its Finish button.
    meta: { inlineError: true },
    // Read back the saved document so the onboarding gate sees the server timestamp.
    onSuccess: () => queryClient.refetchQueries({ queryKey: profileKey(uid) }),
  });
}

/**
 * Save profile edits to Firestore, then read the document back. The mutation only counts as
 * done once the page has the values Firestore really holds, so what is shown is what is saved.
 */
export function useUpdateProfile() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const uid = user?.uid ?? "";

  return useMutation({
    mutationFn: (changes: ProfileChanges) => updateProfile(uid, changes),
    // Each profile form shows the error under its Save button (SaveStatus).
    meta: { inlineError: true },
    onSuccess: () => queryClient.refetchQueries({ queryKey: profileKey(uid) }),
  });
}
