import { ShieldAlert } from "lucide-react";

import RiskBadge from "@/components/common/RiskBadge";
import ScoreRing from "@/components/visual/ScoreRing";

import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import type { RadarEntityProfile } from "@/types/radar";
import { countryName } from "@/utils/format";
import { RISK_COLOR } from "@/utils/radarMap";

export interface EntityRiskCardProps {
  entity: RadarEntityProfile;
}

function corridorLabel(corridorId: string, language: string): string {
  const [host, home] = corridorId.split("-");
  return `${countryName(host, language)} → ${countryName(home, language)}`;
}

/** Risk badge, flagged badge, and the stats behind them (NF-P3-008). */
export default function EntityRiskCard({ entity }: EntityRiskCardProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";

  return (
    <div className="card-surface card-edge space-y-5 bg-gradient-to-br from-radar-tint via-card to-card p-5 md:p-6">
      <div className="flex flex-wrap items-center gap-4">
        {entity.community_rating !== null && (
          <ScoreRing
            value={(entity.community_rating / 5) * 100}
            color={RISK_COLOR[entity.risk_level]}
            size={72}
            label={t("radar.entity.ratingValue", { rating: entity.community_rating })}
          >
            <span className="text-base">{entity.community_rating}</span>
          </ScoreRing>
        )}
        <div className="flex flex-wrap items-center gap-2">
          <RiskBadge
            level={entity.risk_level === "high" ? "danger" : "caution"}
            className="px-3 py-1 text-sm"
          >
            <span
              aria-hidden="true"
              className="inline-block h-2 w-2 rounded-full"
              style={{ backgroundColor: RISK_COLOR[entity.risk_level] }}
            />
            {t(`radar.entity.risk.${entity.risk_level}`)}
          </RiskBadge>
          {entity.flagged && (
            <span className="inline-flex items-center gap-1.5 rounded-full border border-danger/25 bg-danger-tint px-3 py-1 text-sm font-semibold text-danger-tint-ink">
              <ShieldAlert className="h-4 w-4" aria-hidden="true" />
              {t("radar.entity.flagged")}
            </span>
          )}
        </div>
      </div>

      <dl className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-3">
        <div>
          <dt className="text-xs text-muted-foreground">{t("radar.entity.reportsLabel")}</dt>
          <dd className="text-2xl font-extrabold tabular-nums">{entity.report_count}</dd>
        </div>
        <div>
          <dt className="text-xs text-muted-foreground">{t("radar.entity.incidentsLabel")}</dt>
          <dd className="text-2xl font-extrabold tabular-nums">{entity.incident_count}</dd>
        </div>
        <div className="col-span-2 sm:col-span-1">
          <dt className="text-xs text-muted-foreground">{t("radar.entity.ratingLabel")}</dt>
          <dd className="text-2xl font-extrabold">
            {entity.community_rating === null
              ? t("radar.entity.notRated")
              : t("radar.entity.ratingValue", { rating: entity.community_rating })}
          </dd>
        </div>
      </dl>

      {(entity.corridors.length > 0 || entity.host_countries.length > 0) && (
        <dl className="space-y-2 text-sm">
          {entity.corridors.length > 0 && (
            <div>
              <dt className="inline text-xs text-muted-foreground">
                {t("radar.entity.corridorsLabel")}:{" "}
              </dt>
              <dd className="inline">
                {entity.corridors.map((corridor) => corridorLabel(corridor, language)).join(", ")}
              </dd>
            </div>
          )}
          {entity.host_countries.length > 0 && (
            <div>
              <dt className="inline text-xs text-muted-foreground">
                {t("radar.entity.countriesLabel")}:{" "}
              </dt>
              <dd className="inline">
                {entity.host_countries.map((country) => countryName(country, language)).join(", ")}
              </dd>
            </div>
          )}
        </dl>
      )}
    </div>
  );
}
