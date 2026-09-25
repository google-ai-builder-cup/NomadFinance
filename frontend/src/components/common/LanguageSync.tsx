import { useEffect } from "react";

import { useAuth } from "@/hooks/useAuth";
import { useUserProfile } from "@/hooks/useUser";
import { auth } from "@/lib/firebase";
import i18n from "@/lib/i18n";
import { DEFAULT_LANGUAGE, getDeviceLanguage } from "@/lib/languages";

/**
 * Decides which language the UI uses. Mounted once, next to the router.
 *
 * Signed out: the device language (English unless chosen on the sign-in page).
 * Signed in: the profile's preferred_language. Until onboarding saves one, the current
 * language is left alone so onboarding's own language step isn't overridden.
 */
export default function LanguageSync() {
  const { user, loading } = useAuth();
  const profile = useUserProfile();
  const profileLanguage = profile.data?.preferred_language;

  useEffect(() => {
    if (loading) {
      return;
    }
    if (user === null) {
      void i18n.changeLanguage(getDeviceLanguage());
    } else if (profileLanguage !== undefined) {
      void i18n.changeLanguage(profileLanguage);
    }
  }, [loading, user, profileLanguage]);

  useEffect(() => {
    // Screen readers pick their voice from <html lang>; Firebase sends SMS codes and shows
    // reCAPTCHA in auth.languageCode.
    function apply(language: string) {
      document.documentElement.lang = language;
      auth.languageCode = language;
    }
    apply(i18n.resolvedLanguage ?? DEFAULT_LANGUAGE);
    i18n.on("languageChanged", apply);
    return () => i18n.off("languageChanged", apply);
  }, []);

  return null;
}
