import { Loader2 } from "lucide-react";
import { useEffect, useState } from "react";

import { useFocusOnMount } from "@/hooks/useFocusOnMount";
import { useI18n } from "@/hooks/useI18n";

// A message that is not a scam answers in a few seconds; a scam waits for the explanation, which
// has taken up to 40 s. After this long the screen says so, so a slow answer is not mistaken for a hang.
const SLOW_AFTER_MS = 8000;

export default function AnalyzingProgress() {
  const { t } = useI18n("scam");
  const [slow, setSlow] = useState(false);
  const ref = useFocusOnMount<HTMLDivElement>();

  useEffect(() => {
    const timer = window.setTimeout(() => setSlow(true), SLOW_AFTER_MS);
    return () => window.clearTimeout(timer);
  }, []);

  return (
    <div
      ref={ref}
      role="status"
      aria-live="polite"
      tabIndex={-1}
      className="card-surface space-y-2 p-6 text-center focus:outline-none"
    >
      <Loader2 className="mx-auto h-8 w-8 animate-spin text-primary" aria-hidden="true" />
      <p className="text-base font-bold">{t("analyze.progress.title")}</p>
      <p className="text-sm text-muted-foreground">
        {slow ? t("analyze.progress.slow") : t("analyze.progress.wait")}
      </p>
    </div>
  );
}
