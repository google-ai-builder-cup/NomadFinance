import { ArrowRight } from "lucide-react";
import { useEffect, useState } from "react";
import { Link, Navigate } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import Footer from "@/components/layout/Footer";
import LanguageSelector from "@/components/layout/LanguageSelector";
import { PILLAR_ITEMS } from "@/components/layout/navItems";
import { Button } from "@/components/ui/button";
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

      <header className="flex items-center justify-between px-4 py-4 md:px-8">
        <span className="text-lg font-bold tracking-tight">{t("landing.brand")}</span>
        <LanguageSelector />
      </header>

      <main id="main-content" tabIndex={-1} className="flex-1 focus:outline-none">
        {accountDeleted && (
          <p
            role="status"
            className="mx-auto mt-2 max-w-xl rounded-md border border-input bg-muted/50 p-3 text-center text-sm"
          >
            {t("profile.delete.done")}
          </p>
        )}
        <section className="mx-auto max-w-3xl px-4 py-10 text-center md:py-16">
          <p className="text-sm font-medium text-muted-foreground">{t("landing.hero.eyebrow")}</p>
          <h1 className="mt-3 text-3xl font-bold tracking-tight md:text-5xl">
            {t("landing.hero.title")}
          </h1>
          <p className="mx-auto mt-4 max-w-xl text-muted-foreground md:text-lg">
            {t("landing.hero.subtitle")}
          </p>
          <div className="mt-8 flex justify-center">
            <Button asChild size="lg" className="h-11 w-full sm:w-auto">
              <Link to="/sign-in">
                {t("landing.hero.cta")}
                <ArrowRight className="ml-2 h-4 w-4" aria-hidden="true" />
              </Link>
            </Button>
          </div>
        </section>

        <section aria-labelledby="story-heading" className="border-y bg-muted/40">
          <div className="mx-auto max-w-3xl px-4 py-10 md:py-14">
            <h2 id="story-heading" className="text-2xl font-bold tracking-tight">
              {t("landing.story.heading")}
            </h2>
            <p className="mt-4 text-muted-foreground md:text-lg">{t("landing.story.body")}</p>
          </div>
        </section>

        <section
          aria-labelledby="pillars-heading"
          className="mx-auto max-w-4xl px-4 py-10 md:py-14"
        >
          <h2 id="pillars-heading" className="text-center text-2xl font-bold tracking-tight">
            {t("landing.pillars.heading")}
          </h2>
          <ul className="mt-8 grid grid-cols-1 gap-4 sm:grid-cols-2">
            {PILLAR_ITEMS.map(({ to, icon: Icon, nameKey, descriptionKey }) => (
              <li key={to}>
                {/* Signed out, every pillar leads to sign-in; SignIn reads `from` to send the
                    visitor on to the page they actually wanted once they're authenticated. */}
                <Link
                  to="/sign-in"
                  state={{ from: { pathname: to } }}
                  className="group flex h-full flex-col gap-3 rounded-lg border bg-card p-5 text-card-foreground shadow-sm transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                >
                  <span className="flex h-10 w-10 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
                    <Icon className="h-5 w-5" aria-hidden="true" />
                  </span>
                  <h3 className="text-base font-semibold">{t(nameKey)}</h3>
                  <p className="flex-1 text-sm text-muted-foreground">{t(descriptionKey)}</p>
                  <span className="inline-flex items-center gap-1 text-sm font-medium">
                    {t("landing.pillars.cta")}
                    <ArrowRight
                      className="h-4 w-4 transition-transform group-hover:translate-x-0.5"
                      aria-hidden="true"
                    />
                  </span>
                </Link>
              </li>
            ))}
          </ul>
        </section>

        <section className="border-t bg-primary text-primary-foreground">
          <div className="mx-auto flex max-w-3xl flex-col items-center gap-4 px-4 py-10 text-center md:py-14">
            <h2 className="text-2xl font-bold tracking-tight">{t("landing.finalCta.heading")}</h2>
            <p className="text-primary-foreground/80">{t("landing.finalCta.subtitle")}</p>
            <Button asChild size="lg" variant="secondary" className="h-11">
              <Link to="/sign-in">{t("landing.finalCta.button")}</Link>
            </Button>
          </div>
        </section>
      </main>

      <Footer />
    </div>
  );
}
