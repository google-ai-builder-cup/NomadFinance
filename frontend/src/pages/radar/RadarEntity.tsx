import { ArrowLeft } from "lucide-react";
import { Link, useParams } from "react-router-dom";

import LoadingSpinner from "@/components/common/LoadingSpinner";
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
    <Button asChild variant="ghost" className="-ml-2 h-9 gap-1.5">
      <Link to="/radar">
        <ArrowLeft className="h-4 w-4" aria-hidden="true" />
        {t("radar.entity.back")}
      </Link>
    </Button>
  );

  if (isPending) {
    return <LoadingSpinner label={t("common.loading")} className="py-16" />;
  }
  if (isError) {
    return (
      <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">{t("radar.entity.loadError")}</p>
        <Button onClick={refetch}>{t("common.retry")}</Button>
      </div>
    );
  }
  if (entity === null) {
    return (
      <div className="mx-auto max-w-3xl space-y-6">
        {backLink}
        <p className="text-sm text-muted-foreground">{t("radar.entity.notFound")}</p>
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      {backLink}

      <header className="space-y-1">
        <p className="text-sm text-muted-foreground">
          {t(`radar.report.who.types.${entity.entity_type}`)}
        </p>
        <h1 className="text-2xl font-bold tracking-tight">{entity.name}</h1>
      </header>

      <EntityRiskCard entity={entity} />

      <section aria-labelledby="radar-entity-reports" className="space-y-3">
        <h2 id="radar-entity-reports" className="text-lg font-semibold">
          {t("radar.entity.reportsHeading")}
        </h2>
        {reports.isPending ? (
          <LoadingSpinner label={t("common.loading")} className="py-8" />
        ) : reports.isError ? (
          <div role="alert" className="flex flex-col items-start gap-2 text-sm">
            <p className="text-destructive">{t("radar.entity.reportsLoadError")}</p>
            <Button size="sm" variant="outline" onClick={() => void reports.refetch()}>
              {t("common.retry")}
            </Button>
          </div>
        ) : (
          <EntityReportList reports={reports.data ?? []} />
        )}
      </section>
    </div>
  );
}
