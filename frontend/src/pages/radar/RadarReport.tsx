import { Flag } from "lucide-react";
import { useRef } from "react";

import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
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
  // Two taps in the same instant both pass `pending`, which only updates after a render, and
  // each would store the report: the first call holds the form until it ends.
  const sending = useRef(false);

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
      <div className="mx-auto max-w-2xl">
        <ReportConfirmation result={submit.data} onAnother={() => submit.reset()} />
      </div>
    );
  }

  const preferred = profile.data?.preferred_language;
  return (
    <div className="space-y-5">
      <PageHeader
        pillar="radar"
        icon={Flag}
        title={t("radar.report.title")}
        description={t("radar.report.subtitle")}
        compact
      />
      <div className="mx-auto max-w-2xl">
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
          onSubmit={(report, files) => {
            if (sending.current) {
              return;
            }
            sending.current = true;
            submit.mutate(
              { report, files },
              {
                onSettled: () => {
                  sending.current = false;
                },
              }
            );
          }}
        />
      </div>
    </div>
  );
}
