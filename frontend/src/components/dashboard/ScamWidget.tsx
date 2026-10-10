import WidgetCard from "@/components/dashboard/WidgetCard";
import type { ModuleItem } from "@/components/layout/navItems";
import { useI18n } from "@/hooks/useI18n";
import { useLatestScamCheck } from "@/hooks/useScamChecks";
import { useUiLanguage } from "@/hooks/useUiLanguage";
import { scamCardState } from "@/utils/scamCardState";
import { relativeTime } from "@/utils/relativeTime";

/**
 * The Scam Check card on the signed-in home (NF-HR-002): what the worker's last check found, or
 * an invitation to make the first one. The strings are the shared ones, not the Scam namespace's:
 * the dashboard must not download that namespace for one card. While the history loads, and if it
 * cannot be read, the card is the plain pitch with its link, so a failed read never takes the way
 * in away.
 */
export default function ScamWidget({ item }: { item: ModuleItem }) {
  const { t } = useI18n();
  const language = useUiLanguage();
  const latest = useLatestScamCheck();
  const state = latest.isSuccess ? scamCardState(latest.data) : null;

  let body = t(item.descriptionKey);
  if (state?.kind === "none") {
    body = t("dashboard.widgets.scam.empty");
  } else if (state?.kind === "last") {
    const result = t(`dashboard.widgets.scam.result.${state.result}`);
    const when = relativeTime(state.at, language);
    body =
      when === null
        ? t("dashboard.widgets.scam.lastNoWhen", { result })
        : t("dashboard.widgets.scam.last", { result, when });
  }

  return (
    <WidgetCard
      icon={item.icon}
      pillar={item.pillar}
      title={t(item.nameKey)}
      to={item.to}
      openLabel={t("dashboard.widgets.scam.open")}
    >
      <p className="text-sm text-muted-foreground">{body}</p>
    </WidgetCard>
  );
}
