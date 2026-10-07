import { useMemo } from "react";

import { useI18n } from "@/hooks/useI18n";
import { splitMessage } from "@/utils/scamHighlight";

export interface HighlightedMessageProps {
  /** The message as the backend returns it: personal values already replaced by tokens. */
  text: string;
  /** The phrases that gave it away, copied from `text`. */
  phrases: readonly string[];
  /** The language the message is in, so a screen reader pronounces it right. */
  language?: string | null;
}

/** The checked message with the wording that gave it away picked out. Only text nodes are
 * rendered, never HTML: the message is whatever a stranger wrote. Suspicious wording is bold and
 * underlined (and announced), not just coloured; each hidden value is a small labelled chip. */
export default function HighlightedMessage({ text, phrases, language }: HighlightedMessageProps) {
  const { t } = useI18n("scam");
  const pieces = useMemo(() => splitMessage(text, phrases), [text, phrases]);
  const lang = language && language !== "other" ? language : undefined;

  return (
    <p lang={lang} className="whitespace-pre-wrap break-words text-sm leading-7">
      {pieces.map((piece, index) => {
        const content = piece.token ? (
          <span className="mx-0.5 inline-flex items-center rounded-md bg-muted px-1.5 py-0.5 text-xs font-semibold text-muted-foreground">
            {t(`result.token.${piece.token}`)}
          </span>
        ) : (
          piece.text
        );
        if (!piece.highlighted) {
          return <span key={index}>{content}</span>;
        }
        return (
          <mark
            key={index}
            className="rounded-sm bg-caution-tint px-0.5 font-bold text-caution-tint-ink underline decoration-wavy decoration-2 underline-offset-4"
          >
            <span className="sr-only">{t("result.phraseFlagged")} </span>
            {content}
          </mark>
        );
      })}
    </p>
  );
}
