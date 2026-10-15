import { useEffect, useState } from "react";
import { Navigate } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import Ecosystem from "@/components/landing/Ecosystem";
import FinalCta from "@/components/landing/FinalCta";
import HowItWorks from "@/components/landing/HowItWorks";
import ImpactSection from "@/components/landing/ImpactSection";
import LandingFooter from "@/components/landing/LandingFooter";
import LandingHeader from "@/components/landing/LandingHeader";
import LandingHero from "@/components/landing/LandingHero";
import LiveStats from "@/components/landing/LiveStats";
import PerformanceBento from "@/components/landing/PerformanceBento";
import PillarsSection from "@/components/landing/PillarsSection";
import PriyaStory from "@/components/landing/PriyaStory";
import ProblemBand from "@/components/landing/ProblemBand";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";
import { accountWasDeleted, clearAccountDeletedNotice } from "@/services/accountService";

// Public marketing page at "/". Signed-in visitors never see it: they're sent straight to
// the dashboard, same as SignIn does for an already-authenticated visit.
export default function Landing() {
  const { user, loading } = useAuth();
  const { t } = useI18n();
  // After deleting an account the person is sent here, so this is where it is confirmed.
  const [accountDeleted] = useState(accountWasDeleted);
  useEffect(() => clearAccountDeletedNotice(), []);

  if (loading) {
    return <LoadingSpinner label={t("common.loading")} fullScreen />;
  }
  if (user) {
    return <Navigate to="/dashboard" replace />;
  }

  return (
    <div className="flex min-h-screen min-h-dvh flex-col">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded-md focus:bg-background focus:px-3 focus:py-2 focus:text-sm focus:shadow"
      >
        {t("layout.skipToContent")}
      </a>
      <LandingHeader />
      <main id="main-content" tabIndex={-1} className="flex-1 focus:outline-none">
        {accountDeleted && (
          <p
            role="status"
            className="mx-auto mt-4 max-w-xl rounded-xl border border-input bg-muted/60 p-3 text-center text-sm"
          >
            {t("profile.delete.done")}
          </p>
        )}
        <LandingHero />
        <ProblemBand />
        <LiveStats />
        <PerformanceBento />
        <PillarsSection />
        <HowItWorks />
        <PriyaStory />
        <Ecosystem />
        <ImpactSection />
        <FinalCta />
      </main>
      <LandingFooter />
    </div>
  );
}
