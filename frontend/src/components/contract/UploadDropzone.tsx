import { Camera, FileText, Upload, X } from "lucide-react";
import { type ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { type FileRejection, useDropzone } from "react-dropzone";

import { Button } from "@/components/ui/button";
import PillarIllustration from "@/components/visual/PillarIllustration";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

// Mirrors the backend's own checks (app/utils/validators.py, UPLOAD_MAX_BYTES in
// app/config.py): PDF, PNG, JPEG, WebP, HEIC/HEIF, up to 10 MB. The backend is authoritative;
// this only gives quick feedback before a slow upload over a weak connection.
const ACCEPTED_TYPES: Record<string, string[]> = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/webp": [".webp"],
  "image/heic": [".heic"],
  "image/heif": [".heif"],
};
const MAX_SIZE_BYTES = 10 * 1024 * 1024;

function formatBytes(bytes: number): string {
  if (bytes < 1024 * 1024) {
    return `${Math.max(1, Math.round(bytes / 1024))} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

/** An object URL for `file` while it's an image; null for a PDF. Revoked when it changes. */
function useImagePreview(file: File | null): string | null {
  const url = useMemo(() => {
    if (file === null || !file.type.startsWith("image/")) {
      return null;
    }
    return URL.createObjectURL(file);
  }, [file]);

  useEffect(() => {
    return () => {
      if (url) {
        URL.revokeObjectURL(url);
      }
    };
  }, [url]);

  return url;
}

function rejectionMessageKey(rejections: FileRejection[]): string {
  const code = rejections[0]?.errors[0]?.code;
  if (code === "file-too-large") {
    return "contract.upload.errors.tooLarge";
  }
  if (code === "file-invalid-type") {
    return "contract.upload.errors.badType";
  }
  return "contract.upload.errors.generic";
}

export interface UploadDropzoneProps {
  file: File | null;
  onSelect: (file: File) => void;
  onClear: () => void;
  disabled?: boolean;
}

/** File picker for a contract: drag-and-drop, browse, or take a photo. One file at a time. */
export default function UploadDropzone({
  file,
  onSelect,
  onClear,
  disabled = false,
}: UploadDropzoneProps) {
  const { t } = useI18n();
  const [rejectionKey, setRejectionKey] = useState<string | null>(null);
  const previewUrl = useImagePreview(file);

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      const picked = accepted[0];
      if (picked) {
        setRejectionKey(null);
        onSelect(picked);
        return;
      }
      setRejectionKey(rejectionMessageKey(rejected));
    },
    [onSelect]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: ACCEPTED_TYPES,
    maxSize: MAX_SIZE_BYTES,
    multiple: false,
    disabled,
  });

  function handleCameraCapture(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0];
    // Cleared so choosing the same file again (retake) still fires a change event.
    event.target.value = "";
    if (picked) {
      setRejectionKey(null);
      onSelect(picked);
    }
  }

  if (file) {
    return (
      <div className="card-surface flex items-center gap-4 border-contract/40 bg-contract-tint p-4">
        {previewUrl ? (
          <img src={previewUrl} alt="" className="h-16 w-16 shrink-0 rounded-xl object-cover" />
        ) : (
          <FileText className="h-10 w-10 shrink-0 text-contract-ink" aria-hidden="true" />
        )}
        <div className="min-w-0 flex-1">
          <p className="truncate text-sm font-bold">{file.name}</p>
          <p className="text-xs text-muted-foreground">{formatBytes(file.size)}</p>
        </div>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={onClear}
          disabled={disabled}
          aria-label={t("contract.upload.remove")}
        >
          <X className="h-4 w-4" aria-hidden="true" />
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-3">
      <div
        {...getRootProps()}
        className={cn(
          "flex min-h-52 cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-8 text-center transition-colors",
          "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
          isDragActive
            ? "scale-[1.01] border-contract bg-contract-tint"
            : "border-contract/50 bg-contract-tint/60 hover:bg-contract-tint",
          disabled && "pointer-events-none opacity-50"
        )}
      >
        <input {...getInputProps()} aria-label={t("contract.upload.dropzoneLabel")} />
        <div className="w-28" aria-hidden="true">
          <PillarIllustration pillar="contract" />
        </div>
        <Upload className="h-6 w-6 text-contract-ink" aria-hidden="true" />
        <p className="text-base font-bold">{t("contract.upload.dropzoneLabel")}</p>
        <p className="text-xs text-muted-foreground">{t("contract.upload.dropzoneHint")}</p>
      </div>

      <div className="flex items-center gap-3 text-xs text-muted-foreground">
        <div className="h-px flex-1 bg-border" aria-hidden="true" />
        {t("common.or")}
        <div className="h-px flex-1 bg-border" aria-hidden="true" />
      </div>

      <label
        className={cn(
          "flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-xl border border-input bg-card px-4 text-sm font-bold shadow-sm hover:bg-accent",
          "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
          disabled && "pointer-events-none opacity-50"
        )}
      >
        <Camera className="h-4 w-4" aria-hidden="true" />
        {t("contract.upload.takePhoto")}
        <input
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          disabled={disabled}
          onChange={handleCameraCapture}
        />
      </label>

      {rejectionKey && (
        <p role="alert" className="text-sm text-destructive">
          {t(rejectionKey)}
        </p>
      )}
    </div>
  );
}
