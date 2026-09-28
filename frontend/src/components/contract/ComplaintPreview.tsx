import { Copy, Download, ExternalLink, Globe, Mail, MapPin, Phone } from "lucide-react";
import type { LucideIcon } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { toast } from "@/hooks/useToast";
import type { ComplaintChannel, ContractComplaint } from "@/types/contract";
import { copyLetterToClipboard, openPrintableLetter } from "@/utils/complaintActions";
import { languageName } from "@/utils/format";
import i18n from "@/lib/i18n";

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
    return channel.value;
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
 * (docs/pipelines/contract-shield.md, "For the report UI").
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
      className="space-y-4 rounded-lg border bg-card p-6"
    >
      <div className="space-y-1">
        <h2 id="contract-complaint-heading" className="text-lg font-semibold">
          {t("contract.complaint.heading")}
        </h2>
        <p className="text-sm text-muted-foreground">
          {t("contract.complaint.subtitle", {
            authority: complaint.authority_name,
            count: complaint.violation_count,
          })}
        </p>
      </div>

      <p className="text-sm font-medium">{t("contract.complaint.blanksReminder")}</p>

      <div
        lang={previewLanguage}
        className="whitespace-pre-wrap rounded-md border bg-background p-4 text-sm"
      >
        {previewText}
      </div>

      {showsTranslatedPreview && (
        <p className="text-xs text-muted-foreground">
          {t("contract.complaint.sendNote", {
            language: languageName(complaint.letter_language, uiLanguage),
          })}
        </p>
      )}

      <div className="flex flex-wrap gap-2">
        <Button onClick={handleDownload}>
          <Download className="mr-2 h-4 w-4" aria-hidden="true" />
          {t("contract.complaint.download")}
        </Button>
        <Button variant="outline" onClick={() => void handleCopy()}>
          <Copy className="mr-2 h-4 w-4" aria-hidden="true" />
          {t("contract.complaint.copy")}
        </Button>
      </div>

      {(channels.length > 0 || complaint.authority_url) && (
        <div className="space-y-2 border-t pt-4">
          <p className="text-sm font-medium">{t("contract.complaint.whereToSend")}</p>
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
            {complaint.authority_url && (
              <li className="flex items-start gap-2">
                <ExternalLink
                  className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
                <a
                  href={complaint.authority_url}
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
