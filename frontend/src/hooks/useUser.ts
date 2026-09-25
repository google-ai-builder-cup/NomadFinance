import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/hooks/useAuth";
import {
  completeOnboarding,
  getUserProfile,
  updatePreferredLanguage,
} from "@/services/userService";
import type { LanguageCode } from "@/types/enums";
import type { OnboardingAnswers, UserProfile } from "@/types/user";

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
    // Read back the saved document so the onboarding gate sees the server timestamp.
    onSuccess: () => queryClient.refetchQueries({ queryKey: profileKey(uid) }),
  });
}

export function useUpdatePreferredLanguage() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const uid = user?.uid ?? "";

  return useMutation({
    mutationFn: (language: LanguageCode) => updatePreferredLanguage(uid, language),
    onSuccess: (_result, language) =>
      queryClient.setQueryData<UserProfile | null>(profileKey(uid), (profile) =>
        profile ? { ...profile, preferred_language: language } : profile
      ),
  });
}
