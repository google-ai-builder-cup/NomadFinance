import { type FormEvent, useState } from "react";

import { fieldClass } from "@/components/fib/styles";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import type { SavingsLogRequest } from "@/types/fib";
import {
  ACCOUNT_TYPES,
  type AccountType,
  MAX_NOTES_CHARS,
  SAVINGS_DIRECTIONS,
  type SavingsDirection,
} from "@/types/fib";
import { blankToUndefined, LOGGABLE_CURRENCIES, parseAmount } from "@/utils/fibForm";

export interface SavingsFormProps {
  defaultCurrency: string;
  pending: boolean;
  errorKey: string | null;
  onSubmit: (body: SavingsLogRequest) => void;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Quick entry for one savings record (`POST /fib/savings`). */
export default function SavingsForm({
  defaultCurrency,
  pending,
  errorKey,
  onSubmit,
}: SavingsFormProps) {
  const { t } = useI18n();
  const [amountText, setAmountText] = useState("");
  const [currency, setCurrency] = useState(defaultCurrency);
  const [direction, setDirection] = useState<SavingsDirection>("deposit");
  const [accountType, setAccountType] = useState<AccountType | "">("");
  const [notes, setNotes] = useState("");
  const [entryDate, setEntryDate] = useState(today());
  const [problemKey, setProblemKey] = useState<string | null>(null);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (pending) {
      return;
    }
    const amount = parseAmount(amountText, currency);
    if (!amount.ok) {
      setProblemKey(`fib.log.errors.amount.${amount.problem}`);
      return;
    }
    setProblemKey(null);
    onSubmit({
      entry_date: entryDate || undefined,
      amount: amount.amount,
      currency,
      direction,
      account_type: accountType || undefined,
      notes: blankToUndefined(notes),
    });
  }

  const shownKey = problemKey ?? errorKey;

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <fieldset className="grid grid-cols-2 gap-2">
        <legend className="sr-only">{t("fib.log.fields.direction")}</legend>
        {SAVINGS_DIRECTIONS.map((value) => (
          <label
            key={value}
            className={`flex cursor-pointer items-center justify-center gap-2 rounded-lg border p-3 text-sm font-medium has-[:focus-visible]:ring-1 has-[:focus-visible]:ring-ring ${
              direction === value ? "border-primary bg-accent" : "hover:bg-accent"
            }`}
          >
            <input
              type="radio"
              name="savings-direction"
              value={value}
              checked={direction === value}
              onChange={() => setDirection(value)}
              disabled={pending}
              className="sr-only"
            />
            {t(`fib.savingsDirections.${value}`)}
          </label>
        ))}
      </fieldset>

      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label htmlFor="savings-amount" className="text-sm font-medium">
            {t("fib.log.fields.amount")}
          </label>
          <input
            id="savings-amount"
            type="text"
            inputMode="decimal"
            value={amountText}
            onChange={(event) => setAmountText(event.target.value)}
            disabled={pending}
            className={fieldClass}
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="savings-currency" className="text-sm font-medium">
            {t("fib.log.fields.currency")}
          </label>
          <select
            id="savings-currency"
            value={currency}
            onChange={(event) => setCurrency(event.target.value)}
            disabled={pending}
            className={fieldClass}
          >
            {LOGGABLE_CURRENCIES.map((code) => (
              <option key={code} value={code}>
                {code}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="savings-account" className="text-sm font-medium">
          {t("fib.log.fields.accountType")}
        </label>
        <select
          id="savings-account"
          value={accountType}
          onChange={(event) => setAccountType(event.target.value as AccountType)}
          disabled={pending}
          className={fieldClass}
        >
          <option value="">{t("fib.log.fields.chooseAccountType")}</option>
          {ACCOUNT_TYPES.map((value) => (
            <option key={value} value={value}>
              {t(`fib.accountTypes.${value}`)}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="savings-date" className="text-sm font-medium">
          {t("fib.log.fields.entryDate")}
        </label>
        <input
          id="savings-date"
          type="date"
          value={entryDate}
          max={today()}
          onChange={(event) => setEntryDate(event.target.value)}
          disabled={pending}
          className={fieldClass}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="savings-notes" className="text-sm font-medium">
          {t("fib.log.fields.notes")}
        </label>
        <textarea
          id="savings-notes"
          value={notes}
          maxLength={MAX_NOTES_CHARS}
          rows={3}
          onChange={(event) => setNotes(event.target.value)}
          disabled={pending}
          className={`${fieldClass} h-auto py-2`}
        />
      </div>

      {shownKey && (
        <p role="alert" className="text-sm text-destructive">
          {t(shownKey)}
        </p>
      )}

      <Button type="submit" size="lg" className="h-11 w-full" disabled={pending}>
        {pending ? t("fib.log.submitting") : t("fib.log.submit")}
      </Button>
    </form>
  );
}
