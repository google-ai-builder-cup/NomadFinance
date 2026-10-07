import { CircleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { scamErrorView } from "@/utils/scamErrors";

export interface ScamErrorNoticeProps {
  error: unknown;
  onRetry: () => void;
}

/** Why a check failed, in plain words, with "try again" only where trying again can help. */
export default function ScamErrorNotice({ error, onRetry }: ScamErrorNoticeProps) {
  const { t } = useI18n("scam");
  const view = scamErrorView(error);

  return (
    <div
      role="alert"
      className="flex items-start gap-3 rounded-2xl border border-destructive/40 bg-destructive/5 p-4"
    >
      <CircleAlert className="mt-0.5 h-5 w-5 shrink-0 text-destructive" aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-3">
        <p className="text-sm font-semibold">{t(view.messageKey, { minutes: view.waitMinutes })}</p>
        {view.canRetry && (
          <Button type="button" size="sm" variant="outline" onClick={onRetry}>
            {t("common.retry")}
          </Button>
        )}
      </div>
    </div>
  );
}
