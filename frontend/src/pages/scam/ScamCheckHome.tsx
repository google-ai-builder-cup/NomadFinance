import { ScanSearch } from "lucide-react";
import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";

// Stands in until the check screen (NF-SA-015) replaces it. Its own chunk, fetched only once the
// `scam` flag is on for the signed-in user.
export default function ScamCheckHome() {
  const { t } = useI18n();

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-extrabold tracking-tight">{t("nav.scamCheck")}</h1>
      <EmptyState
        icon={ScanSearch}
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
