import { WifiOff } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";

export interface OfflineNoticeProps {
  /** Try to send the waiting answer now, without waiting for the connection to be noticed. */
  onSendNow: () => void;
}

/** The worker's answer is kept on the phone and goes by itself when the connection is back. Not an
 * alert: nothing is wrong with the answer, and it must not take focus from what the worker is
 * doing. A status, so a screen reader says it once. */
export default function OfflineNotice({ onSendNow }: OfflineNoticeProps) {
  const { t } = useI18n("coach");
  return (
    <div
      role="status"
      className="flex shrink-0 items-start gap-3 rounded-2xl border bg-muted/50 p-3"
    >
      <WifiOff className="mt-0.5 h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-2">
        <p className="text-sm font-semibold">{t("offline.notice")}</p>
        <Button type="button" size="sm" variant="outline" className="min-h-11" onClick={onSendNow}>
          {t("offline.sendNow")}
        </Button>
      </div>
    </div>
  );
}
