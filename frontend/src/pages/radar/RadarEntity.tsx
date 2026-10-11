import { ArrowLeft, Radar } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
import PageStateFrame from "@/components/common/PageStateFrame";
import EntityReportList from "@/components/radar/EntityReportList";
import EntityRiskCard from "@/components/radar/EntityRiskCard";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useEntityReports, useRadarEntity } from "@/hooks/useRadar";

/** One business's profile: aggregated stats (NF-P3-003) and its individual reports. */
export default function RadarEntity() {
  const { t } = useI18n();
  const { slug = "" } = useParams<{ slug: string }>();
  const { entity, isPending, isError, refetch } = useRadarEntity(slug);
  const reports = useEntityReports(slug);

  const backLink = (
    <Button asChild variant="outline" className="h-11 gap-1.5 rounded-xl bg-card font-bold">
      <Link to="/radar">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        {t("radar.entity.back")}
      </Link>
    </Button>
  );

  if (isPending) {
    return (
      <PageStateFrame pillar="radar" icon={Radar} title={t("pillars.radar.name")}>
        <LoadingSpinner label={t("common.loading")} className="py-16" />
      </PageStateFrame>
    );
  }
  if (isError) {
    return (
      <PageStateFrame pillar="radar" icon={Radar} title={t("pillars.radar.name")}>
        <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
          <p className="text-sm text-muted-foreground">{t("radar.entity.loadError")}</p>
          <Button onClick={refetch}>{t("common.retry")}</Button>
        </div>
      </PageStateFrame>
    );
  }
  if (entity === null) {
    return (
      <PageStateFrame pillar="radar" icon={Radar} title={t("pillars.radar.name")}>
        {backLink}
        <p className="text-sm text-muted-foreground">{t("radar.entity.notFound")}</p>
      </PageStateFrame>
    );
  }

  return (
    <div className="space-y-5">
      <PageHeader
        pillar="radar"
        icon={Radar}
        title={entity.name}
        description={t(`radar.report.who.types.${entity.entity_type}`)}
        compact
        actions={backLink}
      />

      <div className="grid items-start gap-5 lg:grid-cols-[minmax(0,26rem)_minmax(0,1fr)]">
        <EntityRiskCard entity={entity} />

        <section aria-labelledby="radar-entity-reports" className="space-y-3">
          <h2 id="radar-entity-reports" className="text-lg font-bold tracking-tight">
            {t("radar.entity.reportsHeading")}
          </h2>
          {reports.isPending ? (
            <LoadingSpinner label={t("common.loading")} className="py-8" />
          ) : reports.isError ? (
            <div role="alert" className="flex flex-col items-start gap-2 text-sm">
              <p className="text-danger-ink">{t("radar.entity.reportsLoadError")}</p>
              <Button size="sm" variant="outline" onClick={() => void reports.refetch()}>
                {t("common.retry")}
              </Button>
            </div>
          ) : (
            <EntityReportList reports={reports.data ?? []} />
          )}
        </section>
      </div>
    </div>
  );
}
