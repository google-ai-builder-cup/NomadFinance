import { TriangleAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import type { HostCountry } from "@/types/enums";
import { countryName } from "@/utils/format";

export interface CountryMismatchNoticeProps {
  /** The country the contract itself shows. */
  detected: HostCountry;
  /** The country whose law the check used. */
  used: HostCountry;
  onRecheck: (country: HostCountry) => void;
  pending?: boolean;
  failed?: boolean;
}

/**
 * The check uses the country the worker chose, which starts as the one in their profile. When the
 * contract shows another country, a worker who changed jobs would otherwise be told what their
 * contract says under the wrong country's law, with nothing to say so (NF-HR-004).
 */
export default function CountryMismatchNotice({
  detected,
  used,
  onRecheck,
  pending = false,
  failed = false,
}: CountryMismatchNoticeProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const names = { detected: countryName(detected, language), used: countryName(used, language) };

  return (
    <section
      aria-labelledby="contract-country-mismatch"
      className="flex flex-col gap-3 rounded-2xl border border-caution/40 bg-caution-tint p-4 text-caution-tint-ink sm:flex-row sm:items-center"
    >
      <TriangleAlert className="h-5 w-5 shrink-0" aria-hidden="true" />
      <div className="min-w-0 flex-1 space-y-1">
        <p id="contract-country-mismatch" className="text-sm font-bold">
          {t("contract.report.countryMismatch.body", names)}
        </p>
        {failed && (
          <p role="alert" className="text-sm font-medium text-danger-ink">
            {t("contract.report.countryMismatch.failed")}
          </p>
        )}
      </div>
      <Button
        type="button"
        className="h-11 shrink-0 rounded-xl font-bold"
        disabled={pending}
        onClick={() => onRecheck(detected)}
      >
        {pending
          ? t("contract.report.countryMismatch.working")
          : t("contract.report.countryMismatch.action", names)}
      </Button>
    </section>
  );
}
