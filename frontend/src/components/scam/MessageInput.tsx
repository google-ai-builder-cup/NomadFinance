import { useId } from "react";

import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";
import { countChars, MAX_MESSAGE_CHARS } from "@/utils/scamInput";

export interface MessageInputProps {
  value: string;
  onChange: (value: string) => void;
  disabled?: boolean;
}

/** The paste box. It never cuts a message: over the limit it says so and the worker decides. */
export default function MessageInput({ value, onChange, disabled = false }: MessageInputProps) {
  const { t } = useI18n("scam");
  const id = useId();
  const count = countChars(value);
  const tooLong = count > MAX_MESSAGE_CHARS;

  return (
    <div className="space-y-2">
      <label htmlFor={id} className="text-sm font-bold">
        {t("input.textLabel")}
      </label>
      <textarea
        id={id}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        disabled={disabled}
        rows={8}
        placeholder={t("input.placeholder")}
        aria-invalid={tooLong}
        aria-describedby={`${id}-count`}
        className={cn(
          "min-h-44 w-full resize-y rounded-xl border bg-card px-4 py-3 text-base shadow-sm",
          "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          "disabled:opacity-60",
          // The default field border is 1.3:1 against the card; an empty box is found by its outline.
          tooLong ? "border-danger-ink" : "border-muted-foreground/80"
        )}
      />
      <div id={`${id}-count`} className="flex flex-wrap items-start justify-between gap-2 text-xs">
        {tooLong ? (
          <p role="alert" className="font-semibold text-danger-ink">
            {t("input.tooLong")}
          </p>
        ) : (
          <span />
        )}
        <span
          className={cn(
            "tabular-nums",
            tooLong ? "font-bold text-danger-ink" : "text-muted-foreground"
          )}
        >
          {t("input.counter", { count, max: MAX_MESSAGE_CHARS })}
        </span>
      </div>
    </div>
  );
}
