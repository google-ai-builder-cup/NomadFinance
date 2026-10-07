import { Square, Volume2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import { useSpeech } from "@/hooks/useSpeech";

export interface ReadAloudButtonProps {
  /** The language the text is written in; the voice is chosen for it. */
  language: string;
  /** What to say, one piece per breath. */
  parts: readonly string[];
}

/** Reads the explanation aloud for a worker who finds reading hard. It renders nothing when the
 * device has no voice for the language, rather than offering a button that would stay silent or
 * read a Hindi sentence in an English voice. */
export default function ReadAloudButton({ language, parts }: ReadAloudButtonProps) {
  const { t } = useI18n("scam");
  const { available, speaking, failed, speak, stop } = useSpeech(language);

  if (!available) {
    return null;
  }

  const Icon = speaking ? Square : Volume2;

  return (
    <div className="space-y-2">
      <Button
        type="button"
        variant="outline"
        className="h-auto min-h-11 w-full gap-2 whitespace-normal py-2 text-base font-bold"
        onClick={() => (speaking ? stop() : speak(parts))}
      >
        <Icon className="h-5 w-5 shrink-0" aria-hidden="true" />
        {speaking ? t("result.stopReading") : t("result.readAloud")}
      </Button>
      {failed && (
        <p role="status" className="text-sm font-semibold text-danger-ink">
          {t("result.readAloudFailed")}
        </p>
      )}
    </div>
  );
}
