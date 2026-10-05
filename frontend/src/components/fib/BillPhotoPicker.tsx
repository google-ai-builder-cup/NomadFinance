import { Camera, FileText, Upload, X } from "lucide-react";
import { type ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { type FileRejection, useDropzone } from "react-dropzone";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

// Mirrors the bill scan endpoint's own checks (app/api/v1/fib.py, app/config.py's
// upload_max_bytes): PDF, PNG, JPEG, WebP, HEIC/HEIF, up to 10 MB. Same constraint as a
// contract upload (`UploadDropzone`), kept as its own copy: the two pillars' copy and
// behavior already diverge (one file at a time here, stored the moment it's read).
const ACCEPTED_TYPES: Record<string, string[]> = {
  "application/pdf": [".pdf"],
  "image/png": [".png"],
  "image/jpeg": [".jpg", ".jpeg"],
  "image/webp": [".webp"],
  "image/heic": [".heic"],
  "image/heif": [".heif"],
};
const MAX_SIZE_BYTES = 10 * 1024 * 1024;

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

function rejectionKey(rejections: FileRejection[]): string {
  const code = rejections[0]?.errors[0]?.code;
  if (code === "file-too-large") {
    return "fib.bill.scan.errors.tooLarge";
  }
  if (code === "file-invalid-type") {
    return "fib.bill.scan.errors.badType";
  }
  return "fib.bill.scan.errors.generic";
}

export interface BillPhotoPickerProps {
  file: File | null;
  onSelect: (file: File) => void;
  onClear: () => void;
  disabled?: boolean;
}

/** Photo picker for a bill: drag-and-drop, browse, or take a photo. One file at a time. */
export default function BillPhotoPicker({
  file,
  onSelect,
  onClear,
  disabled = false,
}: BillPhotoPickerProps) {
  const { t } = useI18n();
  const [errorKey, setErrorKey] = useState<string | null>(null);
  const previewUrl = useImagePreview(file);

  const onDrop = useCallback(
    (accepted: File[], rejected: FileRejection[]) => {
      const picked = accepted[0];
      if (picked) {
        setErrorKey(null);
        onSelect(picked);
        return;
      }
      setErrorKey(rejectionKey(rejected));
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
      setErrorKey(null);
      onSelect(picked);
    }
  }

  if (file) {
    return (
      <div className="card-surface flex items-center gap-4 border-identity/40 bg-identity-tint p-4">
        {previewUrl ? (
          <img src={previewUrl} alt="" className="h-16 w-16 shrink-0 rounded object-cover" />
        ) : (
          <FileText className="h-10 w-10 shrink-0 text-muted-foreground" aria-hidden="true" />
        )}
        <p className="min-w-0 flex-1 truncate text-sm font-medium">{file.name}</p>
        <Button
          type="button"
          variant="ghost"
          size="icon"
          onClick={onClear}
          disabled={disabled}
          aria-label={t("fib.bill.scan.remove")}
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
          "flex min-h-32 cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-6 text-center transition-colors",
          "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
          isDragActive
            ? "border-identity bg-identity-tint"
            : "border-identity/50 bg-identity-tint/60 hover:bg-identity-tint",
          disabled && "pointer-events-none opacity-50"
        )}
      >
        <input {...getInputProps()} aria-label={t("fib.bill.scan.dropzoneLabel")} />
        <Upload className="h-7 w-7 text-identity-ink" aria-hidden="true" />
        <p className="text-sm font-bold">{t("fib.bill.scan.dropzoneLabel")}</p>
        <p className="text-xs text-muted-foreground">{t("fib.bill.scan.dropzoneHint")}</p>
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
        {t("fib.bill.scan.takePhoto")}
        <input
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          disabled={disabled}
          onChange={handleCameraCapture}
        />
      </label>

      {errorKey && (
        <p role="alert" className="text-sm text-destructive">
          {t(errorKey)}
        </p>
      )}
    </div>
  );
}
