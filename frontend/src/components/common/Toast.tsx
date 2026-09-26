import { CircleAlert, Info, X } from "lucide-react";
import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { dismissToast, type Toast, useToasts } from "@/hooks/useToast";
import { cn } from "@/lib/utils";

/**
 * Where toasts appear. Mounted once in main.tsx, outside the error boundary, so a toast (for
 * example "New version available") still shows over the crash screen.
 */
export default function Toaster() {
  const { t } = useI18n();
  const toasts = useToasts();

  return (
    <section
      aria-label={t("toast.region")}
      // Above the phone tab bar (h-16); bottom-right on wider screens.
      className="pointer-events-none fixed inset-x-0 bottom-20 z-50 flex justify-center px-4 md:inset-x-auto md:bottom-4 md:right-4 md:w-96 md:px-0"
    >
      {/* The live region exists before any toast, so screen readers announce each new one. */}
      <ol aria-live="polite" className="flex w-full max-w-sm flex-col gap-2">
        {toasts.map((item) => (
          <ToastItem key={item.id} toast={item} />
        ))}
      </ol>
    </section>
  );
}

function ToastItem({ toast: item }: { toast: Toast }) {
  const { t } = useI18n();
  // Hover or keyboard focus holds the toast open, so it can't vanish while being read or used.
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (item.duration === null || paused) {
      return;
    }
    const timer = window.setTimeout(() => dismissToast(item.id), item.duration);
    return () => window.clearTimeout(timer);
  }, [item, paused]);

  const Icon = item.variant === "error" ? CircleAlert : Info;

  return (
    <li
      className={cn(
        "pointer-events-auto flex items-start gap-3 rounded-lg border bg-card p-3 text-card-foreground shadow-lg animate-in fade-in slide-in-from-bottom-2 motion-reduce:animate-none",
        item.variant === "error" && "border-destructive/40"
      )}
      onMouseEnter={() => setPaused(true)}
      onMouseLeave={() => setPaused(false)}
      onFocus={() => setPaused(true)}
      onBlur={() => setPaused(false)}
    >
      <Icon
        className={cn(
          "mt-0.5 h-5 w-5 shrink-0",
          item.variant === "error" ? "text-destructive" : "text-primary"
        )}
        aria-hidden="true"
      />
      <p className="min-w-0 flex-1 text-sm">{t(item.messageKey)}</p>
      {item.action !== undefined && (
        <Button
          size="sm"
          variant="outline"
          onClick={() => {
            item.action?.onClick();
            dismissToast(item.id);
          }}
        >
          {t(item.action.labelKey)}
        </Button>
      )}
      <Button
        variant="ghost"
        size="icon"
        className="-my-1 h-8 w-8 shrink-0"
        aria-label={t("toast.dismiss")}
        title={t("toast.dismiss")}
        onClick={() => {
          item.onDismiss?.();
          dismissToast(item.id);
        }}
      >
        <X className="h-4 w-4" aria-hidden="true" />
      </Button>
    </li>
  );
}
