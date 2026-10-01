import FIBProgressWidget from "@/components/dashboard/FIBProgressWidget";
import RadarAlertsWidget from "@/components/dashboard/RadarAlertsWidget";
import RecentContractsWidget from "@/components/dashboard/RecentContractsWidget";
import RemittanceShortcutWidget from "@/components/dashboard/RemittanceShortcutWidget";
import { useAuth } from "@/hooks/useAuth";
import { useI18n } from "@/hooks/useI18n";

/** Signed-in home: a live widget per pillar — recent contracts, a remittance shortcut, radar
 * alerts, Financial Identity progress (NF-P3-019). Each widget loads independently, so a slow
 * or empty one never blocks the others. */
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
        <div className="grid gap-4 sm:grid-cols-2">
          <RecentContractsWidget />
          <RemittanceShortcutWidget />
          <RadarAlertsWidget />
          <FIBProgressWidget />
        </div>
      </section>
    </div>
  );
}
