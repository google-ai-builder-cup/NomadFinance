import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import type { PillarItem } from "@/components/layout/navItems";
import PageHeader from "@/components/common/PageHeader";
import { Button } from "@/components/ui/button";
import StatusIllustration from "@/components/visual/StatusIllustration";
import { useI18n } from "@/hooks/useI18n";

export interface ComingSoonProps {
  pillar: PillarItem;
}

// Stands in for a pillar's real page until its own task replaces the route element.
export default function ComingSoon({ pillar }: ComingSoonProps) {
  const { t } = useI18n();

  return (
    <div className="space-y-5">
      <PageHeader
        pillar={pillar.pillar}
        icon={pillar.icon}
        title={t(pillar.nameKey)}
        description={t(pillar.descriptionKey)}
      />
      <EmptyState
        icon={pillar.icon}
        title={t("comingSoon.title")}
        description={t("comingSoon.description")}
        illustration={<StatusIllustration variant="soon" />}
        action={
          <Button asChild variant="outline">
            <Link to="/dashboard">{t("comingSoon.backToDashboard")}</Link>
          </Button>
        }
      />
    </div>
  );
}
