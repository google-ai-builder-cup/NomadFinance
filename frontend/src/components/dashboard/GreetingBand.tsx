import { ArrowLeftRight, Fingerprint, Flag, Languages, ShieldCheck } from "lucide-react";
import { MODULE_ITEMS } from "@/components/layout/navItems";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import AnimatedBackground from "@/components/visual/AnimatedBackground";
import PillarIllustration from "@/components/visual/PillarIllustration";
import { useAuth } from "@/hooks/useAuth";
import { useFeatureFlags } from "@/hooks/useFeatureFlag";
import { useI18n } from "@/hooks/useI18n";
import { useUserProfile } from "@/hooks/useUser";
import i18n from "@/lib/i18n";
import { SUPPORTED_LANGUAGES } from "@/lib/languages";
import { PILLAR_STYLES } from "@/utils/pillars";

/** The top of the dashboard: a greeting, today's date, the worker's report language and quick
 * actions that lead straight into the pillars: the four of v1.0, then Scam Check and the Coach
 * for a worker they are switched on for. */
export default function GreetingBand() {
  const { user } = useAuth();
  const { t } = useI18n();
  const profile = useUserProfile();
  const { flags } = useFeatureFlags();
  const modules = MODULE_ITEMS.filter(({ flag }) => flags[flag]);
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
      <div className="relative grid grid-cols-[minmax(0,1fr)] items-center gap-3 p-3.5 sm:gap-6 sm:p-6 md:grid-cols-[minmax(0,1fr)_16rem] md:p-8 lg:grid-cols-[minmax(0,1fr)_21rem]">
        <div className="flex min-w-0 flex-col gap-2.5 sm:gap-4">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="text-[13px] font-semibold text-muted-foreground">{today}</span>
            {/* Not on a phone: the language picker in the header already says it, and the badge
                wraps to a line of its own beside a long date (the 360 px limit, NF-HR-009). */}
            {preferred && (
              <Badge tone="info" className="hidden sm:inline-flex">
                <Languages className="h-3.5 w-3.5" aria-hidden="true" />
                {preferred.nativeName}
              </Badge>
            )}
          </div>
          <div className="space-y-1.5">
            <h1 className="text-balance text-[clamp(1.5rem,3.4vw,2.625rem)] font-extrabold leading-tight tracking-tight">
              {firstName
                ? t("dashboard.greeting", { name: firstName })
                : t("dashboard.greetingGeneric")}
            </h1>
            <p className="hidden text-base text-muted-foreground sm:block md:text-lg">
              {t("dashboard.subtitle")}
            </p>
          </div>
          {/* On a phone the actions are one row that scrolls sideways inside the card (the page itself
              does not), so six buttons do not stack to a third of the screen. */}
          <div className="-mx-3.5 flex gap-2 overflow-x-auto px-3.5 pb-1 [scrollbar-width:none] sm:mx-0 sm:flex-wrap sm:gap-2.5 sm:overflow-visible sm:px-0 sm:pb-0 sm:pt-1 [&::-webkit-scrollbar]:hidden">
            <Button
              asChild
              className="h-11 shrink-0 whitespace-nowrap rounded-xl px-4 font-bold sm:h-12 sm:px-5"
            >
              <Link to="/remittance">
                <ArrowLeftRight className="mr-2 h-4 w-4" aria-hidden="true" />
                {t("dashboard.actions.compare")}
              </Link>
            </Button>
            <Button
              asChild
              variant="outline"
              className="h-11 shrink-0 whitespace-nowrap rounded-xl bg-card px-4 font-bold sm:h-12 sm:px-5"
            >
              <Link to="/contract">
                <ShieldCheck className="mr-2 h-4 w-4" aria-hidden="true" />
                {t("dashboard.actions.contract")}
              </Link>
            </Button>
            <Button
              asChild
              variant="outline"
              className="h-11 shrink-0 whitespace-nowrap rounded-xl bg-card px-4 font-bold sm:h-12 sm:px-5"
            >
              <Link to="/radar/report">
                <Flag className="mr-2 h-4 w-4" aria-hidden="true" />
                {t("dashboard.actions.report")}
              </Link>
            </Button>
            <Button
              asChild
              variant="outline"
              className="h-11 shrink-0 whitespace-nowrap rounded-xl bg-card px-4 font-bold sm:h-12 sm:px-5"
            >
              <Link to="/identity/log">
                <Fingerprint className="mr-2 h-4 w-4" aria-hidden="true" />
                {t("fib.dashboard.logActivity")}
              </Link>
            </Button>
            {modules.map(({ to, pillar, icon: Icon }) => (
              <Button
                key={to}
                asChild
                variant="outline"
                className="h-11 shrink-0 whitespace-nowrap rounded-xl bg-card px-4 font-bold sm:h-12 sm:px-5"
              >
                <Link to={to}>
                  <Icon className="mr-2 h-4 w-4" aria-hidden="true" />
                  {t(`dashboard.actions.${pillar}`)}
                </Link>
              </Button>
            ))}
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
          {modules.map(({ pillar, icon: Icon }, index) => (
            <span
              key={pillar}
              className={`absolute flex h-11 w-11 animate-float-slow items-center justify-center rounded-xl text-white shadow-lg ${PILLAR_STYLES[pillar].tile} ${
                index === 0 ? "-right-1 bottom-20" : "bottom-0 left-8"
              }`}
              style={{ animationDelay: `${-1.5 - index}s` }}
            >
              <Icon className="h-5 w-5" />
            </span>
          ))}
        </div>
      </div>
    </section>
  );
}
