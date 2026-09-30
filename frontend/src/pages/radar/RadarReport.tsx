import LoadingSpinner from "@/components/common/LoadingSpinner";
import ReportConfirmation from "@/components/radar/ReportConfirmation";
import ReportForm from "@/components/radar/ReportForm";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useSubmitReport } from "@/hooks/useRadar";
import { useUserProfile } from "@/hooks/useUser";
import { isLanguageCode } from "@/types/enums";
import { defaultCorridor } from "@/utils/corridors";
import { reportFailureKey } from "@/utils/radarForm";

export default function RadarReport() {
  const { t } = useI18n();
  const profile = useUserProfile();
  const submit = useSubmitReport();

  if (profile.isPending) {
    return <LoadingSpinner label={t("common.loading")} className="py-16" />;
  }
  if (profile.isError) {
    return (
      <div role="alert" className="flex flex-col items-center gap-4 py-16 text-center">
        <p className="text-sm text-muted-foreground">{t("radar.report.profileLoadError")}</p>
        <Button onClick={() => void profile.refetch()}>{t("common.retry")}</Button>
      </div>
    );
  }

  if (submit.data) {
    return (
      <div className="mx-auto max-w-lg">
        <ReportConfirmation result={submit.data} onAnother={() => submit.reset()} />
      </div>
    );
  }

  const preferred = profile.data?.preferred_language;
  return (
    <div className="mx-auto max-w-lg space-y-6">
      <header className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">{t("radar.report.title")}</h1>
        <p className="text-sm text-muted-foreground">{t("radar.report.subtitle")}</p>
      </header>
      <ReportForm
        defaults={{
          language: isLanguageCode(preferred) ? preferred : "en",
          hostCountry: profile.data?.host_country ?? null,
          corridorId: profile.data
            ? defaultCorridor(profile.data.host_country, profile.data.home_country)
            : null,
        }}
        pending={submit.isPending}
        errorKey={submit.isError ? reportFailureKey(submit.error) : null}
        onSubmit={(report, files) => submit.mutate({ report, files })}
      />
    </div>
  );
}
