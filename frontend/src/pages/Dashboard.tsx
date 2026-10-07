import GreetingBand from "@/components/dashboard/GreetingBand";
import ModuleWidget from "@/components/dashboard/ModuleWidget";
import FIBProgressWidget from "@/components/dashboard/FIBProgressWidget";
import KpiRow from "@/components/dashboard/KpiRow";
import RadarAlertsWidget from "@/components/dashboard/RadarAlertsWidget";
import RecentContractsWidget from "@/components/dashboard/RecentContractsWidget";
import RemittanceShortcutWidget from "@/components/dashboard/RemittanceShortcutWidget";
import { MODULE_ITEMS } from "@/components/layout/navItems";
import Reveal from "@/components/visual/Reveal";
import { useFeatureFlags } from "@/hooks/useFeatureFlag";
import { useI18n } from "@/hooks/useI18n";

/** Signed-in home: a greeting, four live KPIs, and a widget per pillar — recent contracts, a
 * remittance shortcut, radar alerts, Financial Identity progress (NF-P3-019), then a card for
 * each Future Scope pillar (Scam Check, Financial Coach) that is on for the worker. Every KPI
 * and widget loads independently, so a slow or empty one never blocks the others. */
export default function Dashboard() {
  const { t } = useI18n();
  const { flags } = useFeatureFlags();

  return (
    <div className="space-y-5">
      <GreetingBand />
      <KpiRow />
      <section aria-labelledby="pillars-heading">
        <h2 id="pillars-heading" className="sr-only">
          {t("dashboard.pillarsHeading")}
        </h2>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <Reveal className="h-full">
            <RemittanceShortcutWidget />
          </Reveal>
          <Reveal delay={60} className="h-full">
            <RecentContractsWidget />
          </Reveal>
          <Reveal delay={120} className="h-full">
            <RadarAlertsWidget />
          </Reveal>
          <Reveal delay={180} className="h-full">
            <FIBProgressWidget />
          </Reveal>
          {MODULE_ITEMS.filter(({ flag }) => flags[flag]).map((item, index) => (
            <Reveal key={item.to} delay={240 + index * 60} className="h-full">
              <ModuleWidget item={item} />
            </Reveal>
          ))}
        </div>
      </section>
    </div>
  );
}
