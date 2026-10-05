import { ArrowLeftRight, Flag, Languages, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
    <section className="card-surface card-edge dotted overflow-hidden">
      <div className="flex flex-col gap-4 bg-gradient-to-r from-card from-55% to-transparent p-6 md:p-8">
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
        </div>
      </div>
    </section>
  );
}
