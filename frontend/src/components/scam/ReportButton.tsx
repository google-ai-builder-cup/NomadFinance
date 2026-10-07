import { CircleCheck, Megaphone } from "lucide-react";
import { useState } from "react";
import { Link } from "react-router-dom";

import ReportSheet from "@/components/scam/ReportSheet";
import { Button } from "@/components/ui/button";
import { useFocusOnMount } from "@/hooks/useFocusOnMount";
import { useI18n } from "@/hooks/useI18n";
import { useReportCheck } from "@/hooks/useScamChecks";
import type { ScamReportRequest, ScamResultView } from "@/types/scam";
import { scamEntitySlug } from "@/utils/scamReport";

function SentMessage({ children }: { children: string }) {
  const ref = useFocusOnMount<HTMLParagraphElement>();
  return (
    <p ref={ref} role="status" tabIndex={-1} className="text-sm font-semibold focus:outline-none">
      {children}
    </p>
  );
}

export interface ReportButtonProps {
  result: ScamResultView;
}

/** "Warn other workers": opens the confirmation sheet, sends the report, and from then on stays
 * disabled with a link to the Radar page of this kind of scam. Only a message judged a scam can
 * be reported (the server refuses the rest), so nothing is drawn for one that is not. */
export default function ReportButton({ result }: ReportButtonProps) {
  const { t } = useI18n("scam");
  const [open, setOpen] = useState(false);
  const report = useReportCheck(result.id);

  if (!result.verdict.is_scam || result.verdict.scam_type === null) {
    return null;
  }

  // The first report's own answer when this visit made it; else the rule the backend names it by
  // (a check reported earlier is stored without the slug).
  const slug = report.data?.entity_slug ?? scamEntitySlug(result.verdict.scam_type);
  const done = result.reported || report.isSuccess;
  // Said only for what this visit did; a check reported on an earlier day just shows the button.
  const message = report.isSuccess
    ? t(report.data.already_reported ? "report.already" : "report.thanks")
    : null;

  function send(request: ScamReportRequest) {
    report.mutate(request, { onSuccess: () => setOpen(false) });
  }

  return (
    <section className="card-surface space-y-3 p-4 sm:p-5">
      <p className="text-sm">{t("report.hint")}</p>

      {done ? (
        <div className="space-y-3">
          <Button type="button" variant="outline" className="min-h-11 w-full gap-2" disabled>
            <CircleCheck className="h-4 w-4" aria-hidden="true" />
            {t("report.buttonDone")}
          </Button>
          {message !== null && <SentMessage>{message}</SentMessage>}
          <Button asChild variant="outline" className="min-h-11 w-full">
            <Link to={`/radar/entity/${slug}`}>{t("report.seeInRadar")}</Link>
          </Button>
        </div>
      ) : (
        <Button type="button" className="min-h-11 w-full gap-2" onClick={() => setOpen(true)}>
          <Megaphone className="h-4 w-4" aria-hidden="true" />
          {t("report.button")}
        </Button>
      )}

      {open && !done && (
        <ReportSheet
          result={result}
          pending={report.isPending}
          error={report.error}
          onSend={send}
          onClose={() => {
            report.reset();
            setOpen(false);
          }}
        />
      )}
    </section>
  );
}
