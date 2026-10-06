import { ArrowLeftRight, Fingerprint, Flag, Languages, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import AnimatedBackground from "@/components/visual/AnimatedBackground";
import PillarIllustration from "@/components/visual/PillarIllustration";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";
import { useUserProfile } from "@/hooks/useUser";
import i18n from "@/lib/i18n";
import { SUPPORTED_LANGUAGES } from "@/lib/languages";

/** The top of the dashboard: a greeting, today's date, the worker's report language and three
 * quick actions that lead straight into the pillars. */
export default function GreetingBand() {
  const { user } = useAuth();
  const { t } = useI18n();
  const profile = useUserProfile();
  const language = i18n.resolvedLanguage ?? "en";
  // Only a Google name is worth greeting by; an email or phone number reads badly as a name.
  const firstName = user?.displayName?.split(" ")[0];
  const preferred = SUPPORTED_LANGUAGES.find((l) => l.code === profile.data?.preferred_language);
  const today = new Intl.DateTimeFormat(language, {
    weekday: "long",
    day: "numeric",
    month: "long",
  }).format(new Date());

  return (
    <section className="card-surface card-edge overflow-hidden bg-gradient-to-br from-remit-tint via-card to-card">
      <AnimatedBackground variant="mesh" />
      <div
        aria-hidden="true"
        className="dotted pointer-events-none absolute inset-0 [mask-image:linear-gradient(100deg,transparent_30%,#000)]"
      />
      <div className="relative grid items-center gap-6 p-6 md:grid-cols-[minmax(0,1fr)_16rem] md:p-8 lg:grid-cols-[minmax(0,1fr)_21rem]">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="text-[13px] font-semibold text-muted-foreground">{today}</span>
            {preferred && (
              <Badge tone="info">
                <Languages className="h-3.5 w-3.5" aria-hidden="true" />
                {preferred.nativeName}
              </Badge>
            )}
          </div>
          <div className="space-y-1.5">
            <h1 className="text-balance text-[clamp(1.75rem,3.4vw,2.625rem)] font-extrabold leading-tight tracking-tight">
              {firstName
                ? t("dashboard.greeting", { name: firstName })
                : t("dashboard.greetingGeneric")}
            </h1>
            <p className="text-base text-muted-foreground md:text-lg">{t("dashboard.subtitle")}</p>
          </div>
          <div className="flex flex-wrap gap-2.5 pt-1">
            <Button asChild className="h-12 rounded-xl px-5 font-bold">
              <Link to="/remittance">
                <ArrowLeftRight className="mr-2 h-4 w-4" aria-hidden="true" />
                {t("dashboard.actions.compare")}
              </Link>
            </Button>
            <Button asChild variant="outline" className="h-12 rounded-xl bg-card px-5 font-bold">
              <Link to="/contract">
                <ShieldCheck className="mr-2 h-4 w-4" aria-hidden="true" />
                {t("dashboard.actions.contract")}
              </Link>
            </Button>
            <Button asChild variant="outline" className="h-12 rounded-xl bg-card px-5 font-bold">
              <Link to="/radar/report">
                <Flag className="mr-2 h-4 w-4" aria-hidden="true" />
                {t("dashboard.actions.report")}
              </Link>
            </Button>
            <Button asChild variant="outline" className="h-12 rounded-xl bg-card px-5 font-bold">
              <Link to="/identity/log">
                <Fingerprint className="mr-2 h-4 w-4" aria-hidden="true" />
                {t("fib.dashboard.logActivity")}
              </Link>
            </Button>
          </div>
        </div>
        {/* Decoration only: the pillar illustration with the other pillars floating around it. */}
        <div aria-hidden="true" className="relative hidden md:block">
          <div className="animate-float">
            <PillarIllustration pillar="remit" />
          </div>
          <span className="absolute -left-1 top-3 flex h-12 w-12 animate-float-slow items-center justify-center rounded-2xl bg-contract text-white shadow-lg">
            <ShieldCheck className="h-6 w-6" />
          </span>
          <span className="absolute -bottom-1 right-2 flex h-12 w-12 animate-float items-center justify-center rounded-2xl bg-identity text-white shadow-lg [animation-delay:-2s]">
            <Fingerprint className="h-6 w-6" />
          </span>
          <span className="absolute right-0 top-8 flex h-10 w-10 animate-float-slow items-center justify-center rounded-xl bg-radar text-white shadow-lg [animation-delay:-3s]">
            <Flag className="h-5 w-5" />
          </span>
        </div>
      </div>
    </section>
  );
}
