import { SearchX } from "lucide-react";
import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";

// Sits outside AppShell so it also works for signed-out visitors.
export default function NotFound() {
  const { t } = useI18n();

  return (
    <main className="mx-auto flex min-h-screen min-h-dvh w-full max-w-md flex-col justify-center px-4 py-10">
      <EmptyState
        icon={SearchX}
        title={t("notFound.title")}
        description={t("notFound.description")}
        action={
          <Button asChild>
            <Link to="/dashboard">{t("notFound.backToDashboard")}</Link>
          </Button>
        }
      />
    </main>
  );
}
