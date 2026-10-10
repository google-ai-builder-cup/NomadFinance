import { Bell, Flag, Radar } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
import PageStateFrame from "@/components/common/PageStateFrame";
import CorridorDetails from "@/components/radar/CorridorDetails";
import HeatmapMap from "@/components/radar/HeatmapMap";
import { Button } from "@/components/ui/button";
import PillarIllustration from "@/components/visual/PillarIllustration";
import { useI18n } from "@/hooks/useI18n";
import { useRadarEntities } from "@/hooks/useRadar";
import { cn } from "@/lib/utils";
import { ENTITY_TYPES } from "@/types/radar";
import {
  corridorHeat,
  entitiesOnCorridor,
  type EntityFilter,
  entityMarkers,
  filterEntities,
  HEAT_STYLE,
  type HeatLevel,
} from "@/utils/radarMap";

const LEVELS: readonly HeatLevel[] = [0, 1, 2, 3];
const FILTERS: readonly EntityFilter[] = ["all", ...ENTITY_TYPES];

export default function RadarHeatmap() {
  const { t } = useI18n();
  const entities = useRadarEntities();
  const [filter, setFilter] = useState<EntityFilter>("all");

  const shown = useMemo(() => filterEntities(entities.data ?? [], filter), [entities.data, filter]);
  const corridors = useMemo(() => corridorHeat(shown), [shown]);
  const markers = useMemo(() => entityMarkers(shown), [shown]);

  const reportButton = (
    <Button
      asChild
      className="h-11 rounded-xl bg-radar-deep px-5 font-bold text-white hover:bg-radar-deep/90"
    >
      <Link to="/radar/report">
        <Flag className="mr-2 h-4 w-4" aria-hidden="true" />
        {t("radar.heatmap.report")}
      </Link>
    </Button>
  );
  const alertsButton = (
    <Button asChild variant="outline" className="h-11 gap-1.5 rounded-xl bg-card font-bold">
      <Link to="/radar/alerts">
        <Bell className="h-4 w-4" aria-hidden="true" />
        {t("radar.heatmap.alerts")}
      </Link>
    </Button>
  );

  if (entities.isPending) {
    return (
      <PageStateFrame pillar="radar" icon={Radar} title={t("radar.heatmap.title")}>
        <LoadingSpinner label={t("common.loading")} className="py-16" />
      </PageStateFrame>
    );
  }
  if (entities.isError) {
    return (
      <PageStateFrame pillar="radar" icon={Radar} title={t("radar.heatmap.title")}>
        <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-sm text-muted-foreground">{t("radar.heatmap.loadError")}</p>
          <Button onClick={() => void entities.refetch()}>{t("common.retry")}</Button>
        </div>
      </PageStateFrame>
    );
  }
  if (entities.data.length === 0) {
    return (
      <div className="space-y-5">
        <PageHeader
          pillar="radar"
          icon={Radar}
          title={t("radar.heatmap.title")}
          description={t("radar.heatmap.subtitle")}
          compact
        />
        <EmptyState
          icon={Radar}
          title={t("radar.heatmap.emptyTitle")}
          description={t("radar.heatmap.emptyDescription")}
          illustration={<PillarIllustration pillar="radar" />}
          action={reportButton}
        />
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        pillar="radar"
        icon={Radar}
        title={t("radar.heatmap.title")}
        description={t("radar.heatmap.subtitle")}
        actions={
          <>
            {alertsButton}
            {reportButton}
          </>
        }
      />

      <div
        role="radiogroup"
        aria-label={t("radar.heatmap.filterLabel")}
        className="-mx-4 flex gap-2 overflow-x-auto px-4 pb-1 md:mx-0 md:flex-wrap md:px-0"
      >
        {FILTERS.map((value) => {
          const selected = filter === value;
          return (
            <button
              key={value}
              type="button"
              role="radio"
              aria-checked={selected}
              onClick={() => setFilter(value)}
              className={cn(
                "min-h-11 shrink-0 rounded-full border px-4 text-sm font-bold transition-colors",
                selected
                  ? "border-radar bg-radar-tint text-radar-ink"
                  : "bg-card text-muted-foreground hover:bg-accent"
              )}
            >
              {value === "all"
                ? t("radar.heatmap.filterAll")
                : t(`radar.report.who.types.${value}`)}
            </button>
          );
        })}
      </div>

      {/* The map fills the screen height on a wide display with a glass panel floating over its
          right edge; on a phone the same panel sits under the map as a sheet. */}
      <div className="relative">
        <HeatmapMap corridors={corridors} markers={markers} />
        <aside
          aria-labelledby="radar-corridors"
          className={cn(
            "glass relative z-[500] -mt-6 space-y-4 rounded-t-3xl border p-4 shadow-lg",
            "lg:absolute lg:inset-y-4 lg:right-4 lg:mt-0 lg:w-[23rem] lg:overflow-y-auto lg:rounded-2xl"
          )}
        >
          <h2 id="radar-corridors" className="text-base font-bold tracking-tight">
            {t("radar.heatmap.byCorridor")}
          </h2>
          <ul
            className="flex flex-wrap gap-x-4 gap-y-1.5 text-xs text-muted-foreground"
            aria-label={t("radar.heatmap.legend")}
          >
            {LEVELS.map((level) => (
              <li key={level} className="flex items-center gap-2">
                <span
                  aria-hidden="true"
                  className="inline-block w-5 rounded-full"
                  style={{ height: HEAT_STYLE[level].weight, background: HEAT_STYLE[level].color }}
                />
                {t(`radar.heatmap.level.${level}`)}
              </li>
            ))}
          </ul>
          {/* One column: a row that opens would otherwise stretch its neighbour in a grid. */}
          <ul className="space-y-2">
            {[...corridors]
              .sort((a, b) => b.reportCount - a.reportCount)
              .map((corridor) => (
                <CorridorDetails
                  key={corridor.id}
                  corridorId={corridor.id}
                  level={corridor.level}
                  reportCount={corridor.reportCount}
                  entities={entitiesOnCorridor(shown, corridor.id)}
                />
              ))}
          </ul>
        </aside>
      </div>
    </div>
  );
}
