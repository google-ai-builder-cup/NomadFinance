import { AtSign, Link2, Mail, Phone, UserRound, type LucideIcon } from "lucide-react";

import RiskBadge, { type RiskLevel } from "@/components/common/RiskBadge";
import { Badge } from "@/components/ui/badge";
import { useI18n } from "@/hooks/useI18n";
import type { ScamIndicator } from "@/types/scam";

const KIND_ICONS: Readonly<Record<ScamIndicator["kind"], LucideIcon>> = {
  url: Link2,
  phone: Phone,
  email: Mail,
  handle: AtSign,
  sender: UserRound,
};

// How worrying each flag is. A copy of a real site or a number that bills the caller is the
// sharper warning; the rest are reasons to look twice.
const FLAG_LEVEL: Readonly<Record<string, RiskLevel>> = {
  lookalike: "danger",
  premium_rate: "danger",
  shortener: "caution",
  punycode: "caution",
  unexpected_country: "caution",
};

export interface IndicatorListProps {
  indicators: readonly ScamIndicator[];
}

/** The contact points found in the message: links, numbers, addresses, a sender. Each is shown as
 * plain text and **never as a link**: this is a scammer's address, and one tap must not open it.
 * A flag always has an icon and words, so colour is never the only signal. */
export default function IndicatorList({ indicators }: IndicatorListProps) {
  const { t } = useI18n("scam");

  if (indicators.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <p className="text-sm font-semibold">{t("result.indicators.careful")}</p>
      <ul className="space-y-3">
        {indicators.map((indicator) => {
          const Icon = KIND_ICONS[indicator.kind];
          const seen = indicator.seen;
          return (
            <li key={indicator.id} className="space-y-2 rounded-xl border border-border p-3">
              <p className="flex items-center gap-2 text-xs font-semibold text-muted-foreground">
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                {t(`result.indicators.kind.${indicator.kind}`)}
              </p>
              <code className="block break-all rounded-md bg-muted px-2 py-1.5 text-sm font-semibold">
                {indicator.value}
              </code>
              {(indicator.flags.length > 0 || seen) && (
                <ul className="flex flex-col items-start gap-1.5">
                  {indicator.flags.map((flag) => (
                    <li key={flag}>
                      <RiskBadge
                        level={FLAG_LEVEL[flag] ?? "caution"}
                        className="h-auto whitespace-normal py-1 text-left"
                      >
                        {t(`result.indicators.flag.${flag}`, {
                          domain: indicator.imitates ?? "",
                          defaultValue: flag.replaceAll("_", " "),
                        })}
                      </RiskBadge>
                    </li>
                  ))}
                  {seen && (
                    <li className="flex flex-wrap items-center gap-2 text-xs">
                      <Badge tone="info" className="h-auto whitespace-normal py-1 text-left">
                        {t("result.indicators.seen", { count: seen.reports })}
                      </Badge>
                      {seen.flagged && (
                        <RiskBadge
                          level="danger"
                          className="h-auto whitespace-normal py-1 text-left"
                        >
                          {t("result.indicators.flagged")}
                        </RiskBadge>
                      )}
                    </li>
                  )}
                </ul>
              )}
            </li>
          );
        })}
      </ul>
    </div>
  );
}
