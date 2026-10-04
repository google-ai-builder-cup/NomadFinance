import { lazy, Suspense, useEffect } from "react";

import { useAuth } from "@/hooks/useAuth";
import { auth } from "@/lib/firebase";
import i18n, { setLanguage } from "@/lib/i18n";
import { clearSessionLanguage, DEFAULT_LANGUAGE } from "@/lib/languages";

const ProfileLanguageSync = lazy(() => import("@/components/common/ProfileLanguageSync"));

/**
 * Decides which language the UI uses. Mounted once, next to the router.
 *
 * Signed out: English (the sign-in page selector changes it only until reload).
 * Signed in: a quick switch made in the header this session, else the profile's
 * preferred_language (ProfileLanguageSync). Signing out ends the quick switch.
 */
export default function LanguageSync() {
  const { user, loading } = useAuth();

  useEffect(() => {
    if (!loading && user === null) {
      clearSessionLanguage();
      void setLanguage(DEFAULT_LANGUAGE);
    }
  }, [loading, user]);

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

  return user === null ? null : (
    <Suspense fallback={null}>
      <ProfileLanguageSync />
    </Suspense>
  );
}
