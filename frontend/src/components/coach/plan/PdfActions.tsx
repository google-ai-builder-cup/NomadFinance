import { FileDown, Loader2, Share2 } from "lucide-react";
import { useRef, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { fetchCoachPlanPdf } from "@/services/coachService";
import type { LanguageCode } from "@/types/enums";
import { coachErrorView, toFailure } from "@/utils/coachErrors";
import { canSharePdf, pdfFilename, savePdf, sharePdf } from "@/utils/coachPdf";

type State = "idle" | "making" | "failed" | "pressAgain";

export interface PdfActionsProps {
  planId: string;
  language: LanguageCode;
}

/**
 * The plan as a file. "Download" saves the PDF; "Share" opens the phone's share sheet with the file
 * itself (WhatsApp, e-mail, a helper), and is shown only where the browser can share a file. The PDF
 * comes through the API with the worker's token and is made on the first request in a language, so
 * the first press can take a few seconds; it is kept for the second.
 */
export default function PdfActions({ planId, language }: PdfActionsProps) {
  const { t } = useI18n("coach");
  const [state, setState] = useState<State>("idle");
  const [error, setError] = useState<unknown>(null);
  const kept = useRef<{ language: LanguageCode; blob: Blob } | null>(null);
  const [shareable] = useState(() => canSharePdf());

  async function pdf(): Promise<Blob | null> {
    if (kept.current?.language === language) {
      return kept.current.blob;
    }
    setState("making");
    setError(null);
    try {
      const blob = await fetchCoachPlanPdf(planId, language);
      kept.current = { language, blob };
      return blob;
    } catch (failure) {
      setError(failure);
      setState("failed");
      return null;
    }
  }

  async function download() {
    const blob = await pdf();
    if (blob) {
      savePdf(blob, pdfFilename(language));
      setState("idle");
    }
  }

  async function share() {
    const blob = await pdf();
    if (!blob) {
      return;
    }
    const outcome = await sharePdf(blob, pdfFilename(language), t("plan.pdf.shareTitle"));
    if (outcome === "unsupported") {
      savePdf(blob, pdfFilename(language)); // no share sheet after all: the worker still gets the file
    }
    // The tap was too long ago (the file took a while): the file is ready, one more press shares it.
    setState(outcome === "blocked" ? "pressAgain" : "idle");
  }

  const making = state === "making";
  const view = state === "failed" ? coachErrorView(toFailure(error)) : null;

  return (
    <section aria-labelledby="plan-pdf" className="space-y-3 rounded-2xl border bg-card p-4">
      <h2 id="plan-pdf" className="text-base font-extrabold">
        {t("plan.pdf.heading")}
      </h2>
      <p className="text-sm text-muted-foreground">{t("plan.pdf.help")}</p>
      <div className="flex flex-col gap-2 sm:flex-row">
        <Button
          type="button"
          className="min-h-11 gap-2 font-bold"
          disabled={making}
          aria-busy={making}
          onClick={() => void download()}
        >
          {making ? (
            <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />
          ) : (
            <FileDown className="h-4 w-4" aria-hidden="true" />
          )}
          {t("plan.pdf.download")}
        </Button>
        {shareable && (
          <Button
            type="button"
            variant="outline"
            className="min-h-11 gap-2 font-bold"
            disabled={making}
            onClick={() => void share()}
          >
            <Share2 className="h-4 w-4" aria-hidden="true" />
            {t("plan.pdf.share")}
          </Button>
        )}
      </div>
      <p role="status" className="text-xs text-muted-foreground empty:hidden">
        {making ? t("plan.pdf.making") : state === "pressAgain" ? t("plan.pdf.pressAgain") : null}
      </p>
      {view && (
        <p role="alert" className="text-sm text-danger-ink">
          {t(view.messageKey, { seconds: view.waitSeconds })}
        </p>
      )}
    </section>
  );
}
