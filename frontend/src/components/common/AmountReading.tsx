import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { dottedThousands } from "@/utils/amountReading";
import { formatMoney } from "@/utils/format";

export interface AmountReadingProps {
  /** What the worker typed. */
  text: string;
  currency: string;
  /** Decimals the currency takes, for how the reading is shown. */
  decimals?: number;
}

/** Says how an amount like `1.500` was read (1,500) before it is sent, because the same text on
 * another keyboard means one and a half. Renders nothing when the text has one reading. */
export default function AmountReading({ text, currency, decimals = 2 }: AmountReadingProps) {
  const { t } = useI18n();
  const value = dottedThousands(text);
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
