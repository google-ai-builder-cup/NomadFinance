import { ArrowRight } from "lucide-react";
import { Link } from "react-router-dom";

import { PILLAR_ITEMS } from "@/components/layout/navItems";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";

export default function Dashboard() {
  const { user } = useAuth();
  const { t } = useI18n();
  // Only a Google name is worth greeting by; an email or phone number reads badly as a name.
  const firstName = user?.displayName?.split(" ")[0];

  return (
    <div className="space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">
          {firstName
            ? t("dashboard.greeting", { name: firstName })
            : t("dashboard.greetingGeneric")}
        </h1>
        <p className="text-muted-foreground">{t("dashboard.subtitle")}</p>
      </header>

      <section aria-labelledby="pillars-heading">
        <h2 id="pillars-heading" className="sr-only">
          {t("dashboard.pillarsHeading")}
        </h2>
        <ul className="grid gap-4 sm:grid-cols-2">
          {PILLAR_ITEMS.map(({ to, icon: Icon, nameKey, descriptionKey }) => (
            <li key={to}>
              <Link
                to={to}
                className="group flex h-full flex-col gap-3 rounded-lg border bg-card p-5 text-card-foreground shadow-sm transition-colors hover:bg-accent focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              >
                <span className="flex h-10 w-10 items-center justify-center rounded-md bg-secondary text-secondary-foreground">
                  <Icon className="h-5 w-5" aria-hidden="true" />
                </span>
                <h3 className="text-base font-semibold">{t(nameKey)}</h3>
                <p className="flex-1 text-sm text-muted-foreground">{t(descriptionKey)}</p>
                <span className="inline-flex items-center gap-1 text-sm font-medium">
                  {t("pillars.open")}
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
    </div>
  );
}
