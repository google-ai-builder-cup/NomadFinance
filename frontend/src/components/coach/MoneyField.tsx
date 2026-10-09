import { useId, useState, type FormEvent } from "react";

import QuickReplyChips from "@/components/common/QuickReplyChips";
import { FIELD_CLASS } from "@/components/coach/fieldClasses";
import { Button } from "@/components/ui/button";
import { useDraftFields } from "@/hooks/useCoachDraft";
import { useI18n } from "@/hooks/useI18n";
import {
  COACH_CURRENCIES,
  isAmount,
  parseAmount,
  plainNumber,
  type CoachCurrency,
  type MoneyPeriod,
} from "@/utils/coachInput";

export interface MoneyFieldProps {
  /** Empty for a total (a debt, savings); a salary is "per month", "per week" or "per year". */
  periods: readonly MoneyPeriod[];
  /** Offer "None (0)" as a one-tap answer: a worker with no debt need not type a zero. */
  canBeNone: boolean;
  defaultCurrency: CoachCurrency;
  busy: boolean;
  onSend: (text: string) => void;
}

/** An amount, its currency and, for pay, how often. The answer is written as one sentence
 * ("4200 AUD per month") that the server reads the same way as typed words. */
export default function MoneyField({
  periods,
  canBeNone,
  defaultCurrency,
  busy,
  onSend,
}: MoneyFieldProps) {
  const { t } = useI18n("coach");
  const id = useId();
  // An empty currency or period is "not chosen yet": the defaults apply and nothing is kept.
  const [fields, change] = useDraftFields("money", { amount: "", currency: "", period: "" });
  const amount = fields.amount;
  const currency = (COACH_CURRENCIES as readonly string[]).includes(fields.currency)
    ? (fields.currency as CoachCurrency)
    : defaultCurrency;
  const period = (periods as readonly string[]).includes(fields.period)
    ? (fields.period as MoneyPeriod)
    : (periods[0] ?? "month");
  const setAmount = (value: string) => change({ amount: value });
  const [invalid, setInvalid] = useState(false);

  function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) {
      return;
    }
    const value = parseAmount(amount);
    // Pay is above zero; a debt or savings may be none.
    if (!isAmount(value, { allowZero: canBeNone }) || value === null) {
      setInvalid(true);
      return;
    }
    setInvalid(false);
    setAmount("");
    onSend(
      t(`input.compose.${periods.length > 0 ? period : "once"}`, {
        amount: plainNumber(value),
        currency,
      })
    );
  }

  return (
    <form onSubmit={submit} noValidate className="space-y-2">
      {canBeNone && (
        <QuickReplyChips
          groupLabel={t("input.suggestions")}
          options={[{ id: "none", label: t("input.none") }]}
          disabled={busy}
          onSelect={(option) => onSend(option.label)}
        />
      )}
      <div className="flex gap-2">
        <div className="min-w-0 flex-1">
          <label htmlFor={`${id}-amount`} className="sr-only">
            {t("input.amountLabel")}
          </label>
          <input
            id={`${id}-amount`}
            value={amount}
            onChange={(event) => setAmount(event.target.value)}
            inputMode="decimal"
            autoComplete="off"
            enterKeyHint="send"
            placeholder={t("input.amountLabel")}
            aria-invalid={invalid}
            aria-describedby={invalid ? `${id}-error` : undefined}
            className={FIELD_CLASS}
          />
        </div>
        <div className="w-28 shrink-0">
          <label htmlFor={`${id}-currency`} className="sr-only">
            {t("input.currencyLabel")}
          </label>
          <select
            id={`${id}-currency`}
            value={currency}
            onChange={(event) => change({ currency: event.target.value })}
            className={FIELD_CLASS}
          >
            {COACH_CURRENCIES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </div>
      </div>
      {periods.length > 0 && (
        <QuickReplyChips
          groupLabel={t("input.periodLabel")}
          options={periods.map((value) => ({ id: value, label: t(`input.period.${value}`) }))}
          selectedId={period}
          onSelect={(option) => change({ period: option.id })}
        />
      )}
      {invalid && (
        <p id={`${id}-error`} role="alert" className="text-sm font-semibold text-danger-ink">
          {t(canBeNone ? "input.error.amountOrZero" : "input.error.amount")}
        </p>
      )}
      <Button type="submit" size="lg" className="min-h-11 w-full" disabled={busy}>
        {t("input.send")}
      </Button>
    </form>
  );
}
