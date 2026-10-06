import { GraduationCap } from "lucide-react";
import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";

// Stands in until the chat screen (NF-FC-017) replaces it. Its own chunk, fetched only once the
// `coach` flag is on for the signed-in user.
export default function CoachHome() {
  const { t } = useI18n("coach");

  return (
    <div className="space-y-5">
      <h1 className="text-2xl font-extrabold tracking-tight">{t("home.title")}</h1>
      <EmptyState
        icon={GraduationCap}
        title={t("home.comingSoonTitle")}
        description={t("home.comingSoonDescription")}
        action={
          <Button asChild variant="outline">
            <Link to="/dashboard">{t("home.backToDashboard")}</Link>
          </Button>
        }
      />
    </div>
  );
}
