import { FileText, Upload, X } from "lucide-react";
import { useCallback, useState } from "react";
import { type FileRejection, useDropzone } from "react-dropzone";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { EVIDENCE_TYPES, MAX_EVIDENCE_BYTES, MAX_EVIDENCE_FILES } from "@/utils/radarForm";

export interface EvidencePickerProps {
  files: File[];
  onChange: (files: File[]) => void;
  disabled?: boolean;
}

function rejectionKey(rejections: FileRejection[]): string {
  const code = rejections[0]?.errors[0]?.code;
  if (code === "file-too-large") {
    return "radar.report.evidence.errors.tooLarge";
  }
  if (code === "file-invalid-type") {
    return "radar.report.evidence.errors.badType";
  }
  return "radar.report.evidence.errors.generic";
}

/** Optional photos or documents for a report: up to 5 files, added one batch at a time. */
export default function EvidencePicker({ files, onChange, disabled = false }: EvidencePickerProps) {
  const { t } = useI18n();
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const full = files.length >= MAX_EVIDENCE_FILES;

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      const room = MAX_EVIDENCE_FILES - files.length;
      if (accepted.length > room) {
        setErrorKey("radar.report.evidence.errors.tooMany");
      } else {
        setErrorKey(rejected.length > 0 ? rejectionKey(rejected) : null);
      }
      if (accepted.length > 0) {
        onChange([...files, ...accepted.slice(0, room)]);
      }
    },
    [files, onChange]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: EVIDENCE_TYPES,
    maxSize: MAX_EVIDENCE_BYTES,
    multiple: true,
    disabled: disabled || full,
  });

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={cn(
          "flex min-h-28 cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-6 text-center transition-colors",
          "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
          isDragActive
            ? "border-radar bg-radar-tint"
            : "border-radar/40 bg-radar-tint/50 hover:bg-radar-tint",
          (disabled || full) && "pointer-events-none opacity-50"
        )}
      >
        <input {...getInputProps()} aria-label={t("radar.report.evidence.add")} />
        <Upload className="h-6 w-6 text-radar-ink" aria-hidden="true" />
        <p className="text-sm font-bold">{t("radar.report.evidence.add")}</p>
        <p className="text-xs text-muted-foreground">{t("radar.report.evidence.hint")}</p>
      </div>

      {errorKey && (
        <p role="alert" className="text-sm text-destructive">
          {t(errorKey)}
        </p>
      )}

      {files.length > 0 && (
        <ul className="space-y-2">
          {files.map((file, index) => (
            <li
              key={`${file.name}-${file.size}-${index}`}
              className="flex items-center gap-3 rounded-xl border bg-card p-3"
            >
              <FileText className="h-5 w-5 shrink-0 text-muted-foreground" aria-hidden="true" />
              <span className="min-w-0 flex-1 truncate text-sm">{file.name}</span>
              <Button
                type="button"
                variant="ghost"
                size="icon"
                disabled={disabled}
                onClick={() => onChange(files.filter((_, at) => at !== index))}
                aria-label={t("radar.report.evidence.remove", { name: file.name })}
              >
                <X className="h-4 w-4" aria-hidden="true" />
              </Button>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
