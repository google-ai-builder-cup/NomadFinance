import { Download, X } from "lucide-react";
import { useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useInstallPrompt } from "@/hooks/useInstallPrompt";

const DISMISSED_KEY = "nomadfinance.installPromptDismissed";

/** Banner offering the native install prompt. Renders nothing until Chrome/Edge/Android fires `beforeinstallprompt`, and nothing once the user dismisses it or installs. */
export default function InstallPrompt() {
  const { t } = useI18n();
  const { canInstall, promptInstall } = useInstallPrompt();
  const [dismissed, setDismissed] = useState(() => localStorage.getItem(DISMISSED_KEY) === "true");

  if (!canInstall || dismissed) {
    return null;
  }

  function dismiss() {
    localStorage.setItem(DISMISSED_KEY, "true");
    setDismissed(true);
  }

  return (
    <div className="mx-4 mt-4 flex items-center gap-3 rounded-lg border bg-card p-3 text-card-foreground shadow-sm md:mx-8">
      <Download className="h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
      <div className="min-w-0 flex-1">
        <p className="text-sm font-medium">{t("pwa.installTitle")}</p>
        <p className="text-xs text-muted-foreground">{t("pwa.installDescription")}</p>
      </div>
      <Button size="sm" onClick={() => void promptInstall()}>
        {t("pwa.install")}
      </Button>
      <Button
        variant="ghost"
        size="icon"
        aria-label={t("pwa.dismiss")}
        title={t("pwa.dismiss")}
        onClick={dismiss}
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </Button>
    </div>
  );
}
