import { Bell, Radar } from "lucide-react";
import { useMemo, useState } from "react";
import { Link } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import CorridorDetails from "@/components/radar/CorridorDetails";
import HeatmapMap from "@/components/radar/HeatmapMap";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useRadarEntities } from "@/hooks/useRadar";
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

const selectClass =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base shadow-sm " +
  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring sm:w-64";

const LEVELS: readonly HeatLevel[] = [0, 1, 2, 3];

export default function RadarHeatmap() {
  const { t } = useI18n();
  const entities = useRadarEntities();
  const [filter, setFilter] = useState<EntityFilter>("all");

  const shown = useMemo(() => filterEntities(entities.data ?? [], filter), [entities.data, filter]);
  const corridors = useMemo(() => corridorHeat(shown), [shown]);
  const markers = useMemo(() => entityMarkers(shown), [shown]);

  const reportButton = (
    <Button asChild className="h-11">
      <Link to="/radar/report">{t("radar.heatmap.report")}</Link>
    </Button>
  );
  const alertsButton = (
    <Button asChild variant="outline" className="h-11 gap-1.5">
      <Link to="/radar/alerts">
        <Bell className="h-4 w-4" aria-hidden="true" />
        {t("radar.heatmap.alerts")}
      </Link>
    </Button>
  );

  if (entities.isPending) {
    return <LoadingSpinner label={t("common.loading")} className="py-16" />;
  }
  if (entities.isError) {
    return (
      <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">{t("radar.heatmap.loadError")}</p>
        <Button onClick={() => void entities.refetch()}>{t("common.retry")}</Button>
      </div>
    );
  }
  if (entities.data.length === 0) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        <h1 className="text-2xl font-bold tracking-tight">{t("radar.heatmap.title")}</h1>
        <EmptyState
          icon={Radar}
          title={t("radar.heatmap.emptyTitle")}
          description={t("radar.heatmap.emptyDescription")}
          action={reportButton}
        />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <header className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div className="space-y-1">
          <h1 className="text-2xl font-bold tracking-tight">{t("radar.heatmap.title")}</h1>
          <p className="text-sm text-muted-foreground">{t("radar.heatmap.subtitle")}</p>
        </div>
        <div className="flex gap-2">
          {alertsButton}
          {reportButton}
        </div>
      </header>

      <div className="space-y-1.5">
        <label htmlFor="radar-filter" className="text-sm font-medium">
          {t("radar.heatmap.filterLabel")}
        </label>
        <select
          id="radar-filter"
          value={filter}
          onChange={(event) => setFilter(event.target.value as EntityFilter)}
          className={selectClass}
        >
          <option value="all">{t("radar.heatmap.filterAll")}</option>
          {ENTITY_TYPES.map((type) => (
            <option key={type} value={type}>
              {t(`radar.report.who.types.${type}`)}
            </option>
          ))}
        </select>
      </div>

      <HeatmapMap corridors={corridors} markers={markers} />

      <ul
        className="flex flex-wrap gap-x-4 gap-y-2 text-xs text-muted-foreground"
        aria-label={t("radar.heatmap.legend")}
      >
        {LEVELS.map((level) => (
          <li key={level} className="flex items-center gap-2">
            <span
              aria-hidden="true"
              className="inline-block w-6 rounded-full"
              style={{ height: HEAT_STYLE[level].weight, background: HEAT_STYLE[level].color }}
            />
            {t(`radar.heatmap.level.${level}`)}
          </li>
        ))}
      </ul>

      <section aria-labelledby="radar-corridors" className="space-y-3">
        <h2 id="radar-corridors" className="text-lg font-semibold">
          {t("radar.heatmap.byCorridor")}
        </h2>
        {/* One column: a row that opens would otherwise stretch its neighbour in a two-column grid. */}
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
      </section>
    </div>
  );
}
