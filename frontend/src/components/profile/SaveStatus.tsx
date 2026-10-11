import { Check } from "lucide-react";

import { useI18n } from "@/hooks/useI18n";

export interface SaveStatusProps {
  saving: boolean;
  failed: boolean;
  /** True once Firestore has accepted the change and it was read back. */
  saved: boolean;
}

/** One line under a Save button. It is a live region, so screen readers announce the result. */
export default function SaveStatus({ saving, failed, saved }: SaveStatusProps) {
  const { t } = useI18n();

  if (failed) {
    return (
      <p role="alert" className="text-sm text-danger-ink">
        {t("profile.saveError")}
      </p>
    );
  }
  return (
    <p role="status" aria-live="polite" className="flex min-h-5 items-center gap-1 text-sm">
      {saving && <span className="text-muted-foreground">{t("profile.saving")}</span>}
      {saved && !saving && (
        <>
          <Check className="h-4 w-4 text-primary" aria-hidden="true" />
          <span>{t("profile.saved")}</span>
        </>
      )}
    </p>
  );
}
