import { ChevronRight, ImageIcon, MessageSquareText, ShieldAlert, ShieldCheck } from "lucide-react";
import { Link } from "react-router-dom";

import RiskBadge from "@/components/common/RiskBadge";
import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import type { ScamCheckSummary } from "@/types/scam";
import { formatCheckDate } from "@/utils/scamHistory";
import { riskLevelForSeverity } from "@/utils/risk";

export interface HistoryItemProps {
  check: ScamCheckSummary;
}

/** One past check as a row that opens it: the kind of scam (or that it was not one), a risk badge,
 * the first words of the message, when it was checked, and whether the worker warned others. Every
 * state has an icon and words, so colour is never the only signal. */
export default function HistoryItem({ check }: HistoryItemProps) {
  const { t } = useI18n("scam");
  const date = formatCheckDate(check.created_at, i18n.resolvedLanguage ?? "en");
  const TitleIcon = check.is_scam ? ShieldAlert : ShieldCheck;
  const InputIcon = check.input_type === "screenshot" ? ImageIcon : MessageSquareText;
  const title = check.is_scam
    ? t(`result.type.${check.scam_type ?? "other_scam"}`, {
        defaultValue: (check.scam_type ?? "").replaceAll("_", " "),
      })
    : t("history.notScam");

  return (
    <Link
      to={`/scam-check/history/${encodeURIComponent(check.id)}`}
      className="card-surface flex items-start gap-3 p-4 transition-shadow duration-base hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
    >
      <TitleIcon
        className={
          check.is_scam
            ? "mt-0.5 h-5 w-5 shrink-0 text-danger"
            : "mt-0.5 h-5 w-5 shrink-0 text-safe"
        }
        aria-hidden="true"
      />
      <div className="min-w-0 flex-1 space-y-2">
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5">
          <p className="font-bold">{title}</p>
          {check.is_scam ? (
            <RiskBadge level={riskLevelForSeverity(check.risk_level)}>
              {t(`result.risk.${check.risk_level}`)}
            </RiskBadge>
          ) : (
            <RiskBadge level="safe">{t("result.notScam")}</RiskBadge>
          )}
        </div>
        <p className="line-clamp-2 break-words text-sm text-muted-foreground">{check.excerpt}</p>
        <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 text-xs text-muted-foreground">
          <span>{date}</span>
          <span className="inline-flex items-center gap-1">
            <InputIcon className="h-3.5 w-3.5" aria-hidden="true" />
            {t(check.input_type === "screenshot" ? "history.screenshot" : "history.pasted")}
          </span>
          {check.reported && <Badge tone="info">{t("history.reported")}</Badge>}
        </div>
      </div>
      <ChevronRight className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
    </Link>
  );
}
