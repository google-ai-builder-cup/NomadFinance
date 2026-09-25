import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import type { PillarItem } from "@/components/layout/navItems";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";

export interface ComingSoonProps {
  pillar: PillarItem;
}

// Stands in for a pillar's real page until its own task replaces the route element.
export default function ComingSoon({ pillar }: ComingSoonProps) {
  const { t } = useI18n();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-bold tracking-tight">{t(pillar.nameKey)}</h1>
      <EmptyState
        icon={pillar.icon}
        title={t("comingSoon.title")}
        description={t("comingSoon.description")}
        action={
          <Button asChild variant="outline">
            <Link to="/dashboard">{t("comingSoon.backToDashboard")}</Link>
          </Button>
        }
      />
    </div>
  );
}
