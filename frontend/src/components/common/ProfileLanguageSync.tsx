import { useEffect } from "react";

import { useAuth } from "@/hooks/useAuth";
import { useUserProfile } from "@/hooks/useUser";
import { setLanguage } from "@/lib/i18n";
import { getSessionLanguage } from "@/lib/languages";

/**
 * Applies a signed-in worker's language. Split from LanguageSync because it reads the
 * profile from Firestore, and the signed-out pages should not download that code (NF-P4-003).
 * Until onboarding saves a language, the current one is left alone so onboarding's own
 * language step isn't overridden.
 */
export default function ProfileLanguageSync() {
  const { loading } = useAuth();
  const profileLanguage = useUserProfile().data?.preferred_language;

  useEffect(() => {
    if (!loading && profileLanguage !== undefined) {
      void setLanguage(getSessionLanguage() ?? profileLanguage);
    }
  }, [loading, profileLanguage]);

  return null;
}
