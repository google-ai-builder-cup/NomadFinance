import WidgetCard from "@/components/dashboard/WidgetCard";
import type { ModuleItem } from "@/components/layout/navItems";
import { useI18n } from "@/hooks/useI18n";

/** The home dashboard card of a Future Scope pillar (Scam Check, Financial Coach): its name, a
 * one-line pitch and a link to its page. Shown only while the module's flag is on for the
 * worker, so the page behind the link is always theirs to open. */
export default function ModuleWidget({ item }: { item: ModuleItem }) {
  const { t } = useI18n();
  return (
    <WidgetCard
      icon={item.icon}
      pillar={item.pillar}
      title={t(item.nameKey)}
      to={item.to}
      openLabel={t(`dashboard.widgets.${item.pillar}.open`)}
    >
      <p className="text-sm text-muted-foreground">{t(item.descriptionKey)}</p>
    </WidgetCard>
  );
}
