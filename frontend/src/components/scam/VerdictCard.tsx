import { CircleHelp, ShieldAlert, ShieldCheck } from "lucide-react";
import { useId } from "react";

import RiskBadge from "@/components/common/RiskBadge";
import RiskMeter from "@/components/common/RiskMeter";
import HighlightedMessage from "@/components/scam/HighlightedMessage";
import IndicatorList from "@/components/scam/IndicatorList";
import TacticChips from "@/components/scam/TacticChips";
import { Badge } from "@/components/ui/badge";
import { useFocusOnMount } from "@/hooks/useFocusOnMount";
import { useI18n } from "@/hooks/useI18n";
import type { ScamResultView } from "@/types/scam";

/** Below this the card says it is not fully sure (the classifier's own advice: under 0.7 a message
 * is short, unclear or could be real). */
const LOW_CONFIDENCE = 0.7;
/** The backend counts at most this many nearest reports, so a count of it means "or more". */
const REPORT_COUNT_CAP = 10;

export interface VerdictCardProps {
  result: ScamResultView;
  /** Move focus to the title when the card appears (a fresh check just finished). */
  focusOnMount?: boolean;
}

/** The answer to "is this a scam": a risk meter and the kind of scam, the tricks it uses (tap to
 * see how each works), the message with the giveaway wording picked out, and the contact points
 * in it. The explanation and next steps are a separate section (NF-SA-017). Every state has an
 * icon and words, so colour is never the only signal. */
export default function VerdictCard({ result, focusOnMount = false }: VerdictCardProps) {
  const { t } = useI18n("scam");
  const titleId = useId();
  const titleRef = useFocusOnMount<HTMLHeadingElement>(focusOnMount);
  const { verdict, explainer } = result;
  const isScam = verdict.is_scam;
  const TitleIcon = isScam ? ShieldAlert : ShieldCheck;

  const typeLabel = (id: string) =>
    t(`result.type.${id}`, { defaultValue: id.replaceAll("_", " ") });
  const similarTypes = [
    ...new Set(result.similar.map((item) => item.scam_type).filter((id): id is string => !!id)),
  ];
  const reports = result.corridor_report_count ?? 0;

  return (
    <section aria-labelledby={titleId} className="card-surface space-y-5 p-4 sm:p-5">
      <header className="space-y-3">
        <div className="flex items-start gap-3">
          <TitleIcon
            className={
              isScam ? "mt-0.5 h-6 w-6 shrink-0 text-danger" : "mt-0.5 h-6 w-6 shrink-0 text-safe"
            }
            aria-hidden="true"
          />
          <h2
            id={titleId}
            ref={titleRef}
            tabIndex={-1}
            className="text-lg font-extrabold leading-snug focus:outline-none"
          >
            {isScam ? t("result.scamTitle") : t("result.notScamTitle")}
          </h2>
        </div>

        {result.cached && <p className="text-xs text-muted-foreground">{t("result.cached")}</p>}

        {isScam ? (
          <RiskMeter
            severity={verdict.risk_level}
            label={t(`result.risk.${verdict.risk_level}`)}
            meterLabel={t("result.meterLabel")}
          />
        ) : (
          <RiskBadge level="safe">{t("result.notScam")}</RiskBadge>
        )}

        {isScam && verdict.scam_type && (
          <p className="text-sm">
            <span className="block text-xs font-semibold text-muted-foreground">
              {t("result.kindOfScam")}
            </span>
            <strong>{typeLabel(verdict.scam_type)}</strong>
          </p>
        )}

        {verdict.confidence < LOW_CONFIDENCE && (
          <p className="flex items-start gap-2 rounded-xl bg-info-tint px-3 py-2 text-sm text-info-tint-ink">
            <CircleHelp className="mt-0.5 h-4 w-4 shrink-0" aria-hidden="true" />
            {t("result.confidenceLow")}
          </p>
        )}
      </header>

      {isScam && verdict.tactics.length > 0 && (
        <section className="space-y-2" aria-labelledby={`${titleId}-tactics`}>
          <h3 id={`${titleId}-tactics`} className="text-sm font-extrabold">
            {t("result.tacticsTitle")}
          </h3>
          <p className="text-xs text-muted-foreground">{t("result.tacticsHint")}</p>
          <TacticChips
            tactics={verdict.tactics}
            explanations={explainer?.kind === "scam" ? explainer.why_it_works : undefined}
          />
        </section>
      )}

      <section className="space-y-2" aria-labelledby={`${titleId}-message`}>
        <h3 id={`${titleId}-message`} className="text-sm font-extrabold">
          {t("result.messageTitle")}
        </h3>
        {verdict.trigger_phrases.length > 0 && (
          <p className="text-xs text-muted-foreground">{t("result.messageLegend")}</p>
        )}
        <div className="rounded-xl border border-border bg-background p-3">
          <HighlightedMessage
            text={result.redacted_text}
            phrases={verdict.trigger_phrases}
            language={result.message_language}
          />
        </div>
      </section>

      {result.indicators.length > 0 && (
        <section className="space-y-2" aria-labelledby={`${titleId}-contacts`}>
          <h3 id={`${titleId}-contacts`} className="text-sm font-extrabold">
            {t("result.indicators.title")}
          </h3>
          <IndicatorList indicators={result.indicators} />
        </section>
      )}

      {(similarTypes.length > 0 || reports > 0) && (
        <section className="space-y-2" aria-labelledby={`${titleId}-similar`}>
          <h3 id={`${titleId}-similar`} className="text-sm font-extrabold">
            {t("result.similarTitle")}
          </h3>
          {similarTypes.length > 0 && (
            <ul className="flex flex-wrap gap-2">
              {similarTypes.map((id) => (
                <li key={id}>
                  <Badge tone="info" className="h-auto whitespace-normal py-1 text-left">
                    {typeLabel(id)}
                  </Badge>
                </li>
              ))}
            </ul>
          )}
          {reports > 0 && (
            <p className="text-sm">
              {reports >= REPORT_COUNT_CAP
                ? t("result.corridorMax")
                : t("result.corridor", { count: reports })}
            </p>
          )}
        </section>
      )}
    </section>
  );
}
