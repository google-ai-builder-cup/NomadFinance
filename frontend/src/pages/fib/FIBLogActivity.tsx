import { ArrowLeft, Fingerprint } from "lucide-react";
import { Link } from "react-router-dom";

import PageHeader from "@/components/common/PageHeader";
import ActivityLogger from "@/components/fib/ActivityLogger";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";

export default function FIBLogActivity() {
  const { t } = useI18n();

  return (
    <div className="space-y-5">
      <PageHeader
        pillar="identity"
        icon={Fingerprint}
        title={t("fib.log.title")}
        description={t("fib.log.subtitle")}
        compact
        actions={
          <Button asChild variant="outline" className="h-11 rounded-xl bg-card font-bold">
            <Link to="/identity">
              <ArrowLeft className="mr-2 h-4 w-4" aria-hidden="true" />
              {t("fib.dashboard.title")}
            </Link>
          </Button>
        }
      />
      <div className="mx-auto max-w-2xl">
        <ActivityLogger />
      </div>
    </div>
  );
}
