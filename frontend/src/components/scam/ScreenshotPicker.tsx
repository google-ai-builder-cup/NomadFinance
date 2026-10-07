import { Camera, ImageIcon, X } from "lucide-react";
import { type ChangeEvent, useCallback, useEffect, useMemo, useState } from "react";
import { type FileRejection, useDropzone } from "react-dropzone";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { IMAGE_TYPES, MAX_IMAGE_BYTES } from "@/utils/scamInput";

function formatBytes(bytes: number): string {
  return bytes < 1024 * 1024
    ? `${Math.max(1, Math.round(bytes / 1024))} KB`
    : `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function rejectionKey(rejections: FileRejection[]): string {
  const code = rejections[0]?.errors[0]?.code;
  if (code === "file-too-large") {
    return "screenshot.errors.tooLarge";
  }
  return code === "file-invalid-type" ? "screenshot.errors.badType" : "screenshot.errors.generic";
}

export interface ScreenshotPickerProps {
  file: File | null;
  onSelect: (file: File) => void;
  onClear: () => void;
  disabled?: boolean;
}

/** Screenshot of a chat: drop, browse or take a photo. One image; the backend reads it and drops it. */
export default function ScreenshotPicker({
  file,
  onSelect,
  onClear,
  disabled = false,
}: ScreenshotPickerProps) {
  const { t } = useI18n("scam");
  const [problemKey, setProblemKey] = useState<string | null>(null);

  const previewUrl = useMemo(() => (file ? URL.createObjectURL(file) : null), [file]);
  useEffect(() => {
    return () => {
      if (previewUrl) {
        URL.revokeObjectURL(previewUrl);
      }
    };
  }, [previewUrl]);

  const accept = useCallback(
    (picked: File) => {
      setProblemKey(null);
      onSelect(picked);
    },
    [onSelect]
  );

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop: (accepted, rejected) => {
      const picked = accepted[0];
      if (picked) {
        accept(picked);
      } else {
        setProblemKey(rejectionKey(rejected));
      }
    },
    accept: IMAGE_TYPES,
    maxSize: MAX_IMAGE_BYTES,
    multiple: false,
    disabled,
  });

  function handleCamera(event: ChangeEvent<HTMLInputElement>) {
    const picked = event.target.files?.[0];
    // Cleared so retaking the same photo still fires a change event.
    event.target.value = "";
    if (!picked) {
      return;
    }
    // `capture` does not enforce a type or size the way the dropzone does.
    if (!(picked.type in IMAGE_TYPES)) {
      setProblemKey("screenshot.errors.badType");
    } else if (picked.size > MAX_IMAGE_BYTES) {
      setProblemKey("screenshot.errors.tooLarge");
    } else {
      accept(picked);
    }
  }

  if (file) {
    return (
      <div className="card-surface flex items-center gap-4 p-4">
        {previewUrl && (
          <img src={previewUrl} alt="" className="h-20 w-20 shrink-0 rounded-xl object-cover" />
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
          aria-label={t("screenshot.remove")}
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
          "flex min-h-44 cursor-pointer flex-col items-center justify-center gap-2 rounded-2xl border-2 border-dashed px-4 py-8 text-center transition-colors",
          "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
          isDragActive
            ? "border-radar bg-radar-tint"
            : "border-radar/50 bg-radar-tint/60 hover:bg-radar-tint",
          disabled && "pointer-events-none opacity-50"
        )}
      >
        <input {...getInputProps()} aria-label={t("screenshot.dropzoneLabel")} />
        <ImageIcon className="h-7 w-7 text-radar-ink" aria-hidden="true" />
        <p className="text-base font-bold">{t("screenshot.dropzoneLabel")}</p>
        <p className="text-xs text-muted-foreground">{t("screenshot.dropzoneHint")}</p>
      </div>

      <label
        className={cn(
          "flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-xl border border-input bg-card px-4 text-sm font-bold shadow-sm hover:bg-accent",
          "has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-ring",
          disabled && "pointer-events-none opacity-50"
        )}
      >
        <Camera className="h-4 w-4" aria-hidden="true" />
        {t("screenshot.takePhoto")}
        <input
          type="file"
          accept="image/*"
          capture="environment"
          className="sr-only"
          disabled={disabled}
          onChange={handleCamera}
        />
      </label>

      {problemKey && (
        <p role="alert" className="text-sm text-danger-ink">
          {t(problemKey)}
        </p>
      )}
    </div>
  );
}
