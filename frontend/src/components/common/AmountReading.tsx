import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { ambiguousReading } from "@/utils/amountReading";
import { currencyDecimals } from "@/utils/fibForm";
import { formatMoney } from "@/utils/format";

export interface AmountReadingProps {
  /** What the worker typed. */
  text: string;
  currency: string;
  /** Decimals the currency takes; the currency's own when left out. */
  decimals?: number;
}

/** Says how an amount like `5.400` was read (5.40) before it is sent, because the same text on
 * another keyboard means five thousand four hundred. Renders nothing when the text has one reading. */
export default function AmountReading({
  text,
  currency,
  decimals = currencyDecimals(currency),
}: AmountReadingProps) {
  const { t } = useI18n();
  const value = ambiguousReading(text, decimals);
  if (value === null) {
    return null;
  }
  const language = i18n.resolvedLanguage ?? "en";
  return (
    <p role="status" className="text-xs font-semibold text-caution-ink">
      {t("common.amountReading", { amount: formatMoney(value, currency, language, decimals) })}
    </p>
  );
}
