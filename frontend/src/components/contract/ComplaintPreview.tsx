import { Copy, Download, ExternalLink, Globe, Mail, MapPin, Phone } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import BrandMark from "@/components/visual/BrandMark";
import { useI18n } from "@/hooks/useI18n";
import { toast } from "@/hooks/useToast";
import type { ComplaintChannel, ContractComplaint } from "@/types/contract";
import { copyLetterToClipboard, openPrintableLetter } from "@/utils/complaintActions";
import { languageName } from "@/utils/format";
import i18n from "@/lib/i18n";
import { safeWebUrl } from "@/utils/safeUrl";

export interface ComplaintPreviewProps {
  complaint: ContractComplaint;
}

const CHANNEL_ICON: Record<ComplaintChannel["kind"], LucideIcon> = {
  web: Globe,
  email: Mail,
  phone: Phone,
  post: MapPin,
};

function channelHref(channel: ComplaintChannel): string | null {
  if (channel.kind === "web") {
    return safeWebUrl(channel.value);
  }
  if (channel.kind === "email") {
    return `mailto:${channel.value}`;
  }
  if (channel.kind === "phone") {
    return `tel:${channel.value}`;
  }
  return null;
}

/**
 * The complaint letter NF-P2-006 wrote, when a clause broke the law (NF-P2-013). Preview shows
 * `worker_copy` (or `letter_text` when that is null, i.e. already the worker's language);
 * download and copy always use `letter_text`, the one actually addressed to the authority
 * (docs/pipelines/contract-shield.md, "For the report UI"). The preview is laid out on a sheet
 * with a letterhead, like the printed page it becomes.
 */
export default function ComplaintPreview({ complaint }: ComplaintPreviewProps) {
  const { t } = useI18n();
  const previewText = complaint.worker_copy ?? complaint.letter_text;
  const previewLanguage =
    complaint.worker_copy !== null ? complaint.worker_language : complaint.letter_language;
  const uiLanguage = i18n.resolvedLanguage ?? "en";
  const showsTranslatedPreview = complaint.worker_copy !== null;
  const channels = complaint.channels;

  function handleDownload() {
    const opened = openPrintableLetter(complaint.letter_text, complaint.authority_name);
    if (!opened) {
      toast({ messageKey: "contract.complaint.printBlocked", variant: "error" });
    }
  }

  async function handleCopy() {
    try {
      await copyLetterToClipboard(complaint.letter_text);
      toast({ messageKey: "contract.complaint.copied" });
    } catch {
      toast({ messageKey: "contract.complaint.copyFailed", variant: "error" });
    }
  }

  return (
    <section
      aria-labelledby="contract-complaint-heading"
      className="card-surface space-y-4 bg-gradient-to-br from-contract-tint via-card to-card p-5 md:p-6"
    >
      <div className="space-y-1">
        <h2 id="contract-complaint-heading" className="text-lg font-bold tracking-tight">
          {t("contract.complaint.heading")}
        </h2>
        <p className="text-sm text-muted-foreground">
          {t("contract.complaint.subtitle", {
            authority: complaint.authority_name,
            count: complaint.violation_count,
          })}
        </p>
      </div>

      <p className="rounded-xl border border-caution/30 bg-caution-tint p-3 text-sm font-medium text-caution-tint-ink">
        {t("contract.complaint.blanksReminder")}
      </p>

      {/* The sheet stays light in the dark theme too: it stands for the paper that gets printed. */}
      <div className="rounded-md border border-border bg-paper p-5 text-paper-ink shadow-md md:p-7">
        <div className="mb-4 flex items-center gap-2.5 border-b-2 border-contract pb-3">
          <BrandMark size={26} />
          <div>
            <p className="text-sm font-extrabold">{t("landing.brand")}</p>
            <p className="text-[11px] text-paper-muted">{t("contract.complaint.heading")}</p>
          </div>
        </div>
        <div
          lang={previewLanguage}
          className="whitespace-pre-wrap font-serif text-[13.5px] leading-7"
        >
          {previewText}
        </div>
      </div>

      {showsTranslatedPreview && (
        <p className="text-xs text-muted-foreground">
          {t("contract.complaint.sendNote", {
            language: languageName(complaint.letter_language, uiLanguage),
          })}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <Button
          onClick={handleDownload}
          className="h-11 rounded-xl bg-contract-deep px-5 font-bold text-white hover:bg-contract-deep/90"
        >
          <Download className="mr-2 h-4 w-4" aria-hidden="true" />
          {t("contract.complaint.download")}
        </Button>
        <Button
          variant="outline"
          className="h-11 rounded-xl bg-card px-5 font-bold"
          onClick={() => void handleCopy()}
        >
          <Copy className="mr-2 h-4 w-4" aria-hidden="true" />
          {t("contract.complaint.copy")}
        </Button>
      </div>

      {(channels.length > 0 || complaint.authority_url) && (
        <div className="space-y-2 border-t pt-4">
          <p className="text-sm font-bold">{t("contract.complaint.whereToSend")}</p>
          <ul className="space-y-1.5 text-sm">
            {channels.map((channel, index) => {
              const Icon = CHANNEL_ICON[channel.kind];
              const href = channelHref(channel);
              return (
                <li key={index} className="flex items-start gap-2">
                  <Icon
                    className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                    aria-hidden="true"
                  />
                  <span>
                    {href ? (
                      <a
                        href={href}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="underline"
                      >
                        {channel.value}
                      </a>
                    ) : (
                      channel.value
                    )}
                    {channel.note && (
                      <span className="text-muted-foreground"> — {channel.note}</span>
                    )}
                  </span>
                </li>
              );
            })}
            {safeWebUrl(complaint.authority_url) && (
              <li className="flex items-start gap-2">
                <ExternalLink
                  className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
                <a
                  href={safeWebUrl(complaint.authority_url) ?? undefined}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="break-all underline"
                >
                  {complaint.authority_url}
                </a>
              </li>
            )}
          </ul>
        </div>
      )}
    </section>
  );
}
