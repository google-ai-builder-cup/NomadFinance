import RiskBadge from "@/components/common/RiskBadge";
import IndicatorList from "@/components/scam/IndicatorList";
import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import type { RadarScamReport } from "@/types/radar";
import { formatMoney } from "@/utils/format";
import { riskLevelForSeverity } from "@/utils/risk";

export interface ScamReportDetailsProps {
  scam: RadarScamReport;
}

/** What a worker confirmed about a scam when they warned others (NF-SA-018, D-124): how risky it
 * looked, the tricks, the words that gave it away, what it asked for and the contacts they chose to
 * share. A contact is shown as plain text and never as a link: it is a scammer's address. It is
 * one worker's unverified report, and the list above it says so. */
export default function ScamReportDetails({ scam }: ScamReportDetailsProps) {
  const { t } = useI18n("scam");
  const language = i18n.resolvedLanguage ?? "en";
  const amount = scam.details.amount_requested;

  return (
    <div className="mt-3 space-y-3 border-t pt-3">
      <RiskBadge level={riskLevelForSeverity(scam.risk_level)}>
        {t(`result.risk.${scam.risk_level}`)}
      </RiskBadge>

      {scam.tactics.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold text-muted-foreground">{t("radarReport.tactics")}</p>
          <ul className="flex flex-wrap gap-1.5">
            {scam.tactics.map((tactic) => (
              <li key={tactic}>
                <Badge tone="info">
                  {t(`result.tactic.${tactic}.label`, {
                    defaultValue: tactic.replaceAll("_", " "),
                  })}
                </Badge>
              </li>
            ))}
          </ul>
        </div>
      )}

      {scam.trigger_phrases.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold text-muted-foreground">{t("radarReport.phrases")}</p>
          <ul className="space-y-1">
            {scam.trigger_phrases.map((phrase) => (
              <li key={phrase} lang={scam.message_language ?? undefined} className="break-words">
                <strong className="underline decoration-wavy underline-offset-4">{phrase}</strong>
              </li>
            ))}
          </ul>
        </div>
      )}

      {amount && (
        <p className="text-sm">
          <span className="block text-xs font-semibold text-muted-foreground">
            {t("radarReport.asked")}
          </span>
          <strong>{formatMoney(amount.amount, amount.currency, language)}</strong>
        </p>
      )}

      {scam.indicators.length > 0 && (
        <div className="space-y-1.5">
          <p className="text-xs font-semibold text-muted-foreground">{t("radarReport.contacts")}</p>
          <IndicatorList
            indicators={scam.indicators.map((indicator, index) => ({
              ...indicator,
              id: String(index),
              seen: null,
            }))}
          />
        </div>
      )}
    </div>
  );
}
