import { ChevronDown, ShieldAlert } from "lucide-react";
import { useId, useState } from "react";
import { Link } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import EntityReportList from "@/components/radar/EntityReportList";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useEntityReports } from "@/hooks/useRadar";
import i18n from "@/lib/i18n";
import type { CorridorId } from "@/types/enums";
import type { RadarEntityProfile, RadarReportSummary } from "@/types/radar";
import { countryName } from "@/utils/format";
import { HEAT_STYLE, type HeatLevel, RISK_COLOR } from "@/utils/radarMap";

// Enough to read at a glance; the rest is one tap away. Keeps a busy route from becoming a wall.
const REPORTS_SHOWN = 3;
const BUSINESSES_SHOWN = 5;

// Same look for the two actions at the foot of a business, so they line up. 44 px tall to tap.
const linkClass =
  "inline-flex min-h-11 items-center rounded-sm text-sm font-medium underline underline-offset-2 " +
  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring";

function routeLabel(corridorId: string, language: string): string {
  const [host, home] = corridorId.split("-");
  return `${countryName(host, language)} → ${countryName(home, language)}`;
}

interface BusinessProps {
  entity: RadarEntityProfile;
  corridorId: CorridorId;
}

/** One business on the route: who it is, how risky, and what workers reported about it. */
function Business({ entity, corridorId }: BusinessProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const reports = useEntityReports(entity.slug);
  const [showAll, setShowAll] = useState(false);

  const list = reports.data ?? [];
  const visible = showAll ? list : list.slice(0, REPORTS_SHOWN);
  // A business's report count is not split by route, so say when a report is about another one.
  const note = (report: RadarReportSummary): string | null =>
    report.corridor_id !== null && report.corridor_id !== corridorId
      ? t("radar.heatmap.otherRoute", { route: routeLabel(report.corridor_id, language) })
      : null;

  return (
    <div className="space-y-3 rounded-md border bg-background p-3">
      <div className="flex flex-wrap items-start justify-between gap-x-3 gap-y-2">
        <div className="min-w-0 space-y-0.5">
          <p className="break-words font-medium">{entity.name}</p>
          <p className="text-xs text-muted-foreground">
            {t(`radar.report.who.types.${entity.entity_type}`)} ·{" "}
            {t("radar.heatmap.reports", { n: entity.report_count })}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <span
            className="inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium text-white"
            style={{ backgroundColor: RISK_COLOR[entity.risk_level] }}
          >
            {t(`radar.entity.risk.${entity.risk_level}`)}
          </span>
          {entity.flagged && (
            <span className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2.5 py-0.5 text-xs font-medium text-destructive">
              <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />
              {t("radar.entity.flagged")}
            </span>
          )}
        </div>
      </div>

      {reports.isPending && <LoadingSpinner label={t("common.loading")} className="py-2" />}
      {reports.isError && (
        <div role="alert" className="flex flex-wrap items-center gap-2 text-sm">
          <span className="text-muted-foreground">{t("radar.heatmap.reportsLoadError")}</span>
          <Button variant="outline" size="sm" onClick={() => void reports.refetch()}>
            {t("common.retry")}
          </Button>
        </div>
      )}
      {reports.isSuccess && <EntityReportList reports={visible} variant="compact" note={note} />}
      <div className="flex flex-wrap items-center justify-between gap-x-4 gap-y-1 border-t pt-2">
        {reports.isSuccess && list.length > REPORTS_SHOWN && (
          <button
            type="button"
            onClick={() => setShowAll((previous) => !previous)}
            className={linkClass}
          >
            {showAll
              ? t("radar.heatmap.showFewerReports")
              : t("radar.heatmap.showAllReports", { n: list.length })}
          </button>
        )}
        <Link to={`/radar/entity/${entity.slug}`} className={linkClass}>
          {t("radar.heatmap.viewProfile")}
        </Link>
      </div>
    </div>
  );
}

export interface CorridorDetailsProps {
  corridorId: CorridorId;
  level: HeatLevel;
  reportCount: number;
  /** The businesses on this route, most reports first. */
  entities: readonly RadarEntityProfile[];
  /** Open from the start; for tests and for a link that wants it open. */
  defaultOpen?: boolean;
}

/**
 * One money route as a row that opens to show who was reported on it and what was reported
 * (the map above stays as it is). Reports load when the row is opened, not before.
 */
export default function CorridorDetails({
  corridorId,
  level,
  reportCount,
  entities,
  defaultOpen = false,
}: CorridorDetailsProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const panelId = useId();
  const [open, setOpen] = useState(defaultOpen);
  const [allBusinesses, setAllBusinesses] = useState(false);

  const shown = allBusinesses ? entities : entities.slice(0, BUSINESSES_SHOWN);

  return (
    <li className="rounded-lg border bg-card">
      <button
        type="button"
        aria-expanded={open}
        aria-controls={panelId}
        onClick={() => setOpen((previous) => !previous)}
        className="flex min-h-12 w-full items-center gap-3 rounded-lg p-3 text-left focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
      >
        <span
          aria-hidden="true"
          className="h-3 w-3 shrink-0 rounded-full"
          style={{ background: HEAT_STYLE[level].color }}
        />
        <span className="min-w-0 flex-1 text-sm font-medium">
          {routeLabel(corridorId, language)}
        </span>
        <span className="shrink-0 text-sm text-muted-foreground">
          {t("radar.heatmap.reports", { n: reportCount })}
        </span>
        <ChevronDown
          aria-hidden="true"
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${
            open ? "rotate-180" : ""
          }`}
        />
      </button>

      {open && (
        <div id={panelId} className="space-y-3 border-t p-3">
          {entities.length === 0 ? (
            <div className="flex flex-col items-start gap-3">
              <p className="text-sm text-muted-foreground">{t("radar.heatmap.noBusinesses")}</p>
              <Button asChild variant="outline" size="sm">
                <Link to="/radar/report">{t("radar.heatmap.report")}</Link>
              </Button>
            </div>
          ) : (
            <>
              <p className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                {t("radar.heatmap.businessesHeading")}
              </p>
              {shown.map((entity) => (
                <Business key={entity.slug} entity={entity} corridorId={corridorId} />
              ))}
              {entities.length > BUSINESSES_SHOWN && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-9 px-2"
                  onClick={() => setAllBusinesses((previous) => !previous)}
                >
                  {allBusinesses
                    ? t("radar.heatmap.showFewerBusinesses")
                    : t("radar.heatmap.showMoreBusinesses", {
                        n: entities.length - BUSINESSES_SHOWN,
                      })}
                </Button>
              )}
            </>
          )}
        </div>
      )}
    </li>
  );
}
