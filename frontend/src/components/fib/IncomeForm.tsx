import { type FormEvent, useState } from "react";

import { fieldClass, submitClass } from "@/components/fib/styles";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import type { IncomeLogRequest } from "@/types/fib";
import {
  INCOME_CATEGORIES,
  type IncomeCategory,
  MAX_EMPLOYER_CHARS,
  MAX_NOTES_CHARS,
} from "@/types/fib";
import { blankToUndefined, LOGGABLE_CURRENCIES, parseAmount } from "@/utils/fibForm";

export interface IncomeFormProps {
  defaultCurrency: string;
  pending: boolean;
  errorKey: string | null;
  onSubmit: (body: IncomeLogRequest) => void;
}

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Quick entry for one income record (`POST /fib/income`). */
export default function IncomeForm({
  defaultCurrency,
  pending,
  errorKey,
  onSubmit,
}: IncomeFormProps) {
  const { t } = useI18n();
  const [amountText, setAmountText] = useState("");
  const [currency, setCurrency] = useState(defaultCurrency);
  const [category, setCategory] = useState<IncomeCategory | "">("");
  const [employerName, setEmployerName] = useState("");
  const [notes, setNotes] = useState("");
  const [entryDate, setEntryDate] = useState(today());
  const [problemKey, setProblemKey] = useState<string | null>(null);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (pending) {
      return;
    }
    if (!category) {
      setProblemKey("fib.log.errors.categoryRequired");
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
      category,
      employer_name: blankToUndefined(employerName),
      notes: blankToUndefined(notes),
    });
  }

  const shownKey = problemKey ?? errorKey;

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <div className="grid grid-cols-2 gap-3">
        <div className="space-y-1.5">
          <label htmlFor="income-amount" className="text-sm font-bold">
            {t("fib.log.fields.amount")}
          </label>
          <input
            id="income-amount"
            type="text"
            inputMode="decimal"
            value={amountText}
            onChange={(event) => setAmountText(event.target.value)}
            disabled={pending}
            className={fieldClass}
          />
        </div>
        <div className="space-y-1.5">
          <label htmlFor="income-currency" className="text-sm font-bold">
            {t("fib.log.fields.currency")}
          </label>
          <select
            id="income-currency"
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
        <label htmlFor="income-category" className="text-sm font-bold">
          {t("fib.log.fields.category")}
        </label>
        <select
          id="income-category"
          value={category}
          onChange={(event) => setCategory(event.target.value as IncomeCategory)}
          disabled={pending}
          className={fieldClass}
        >
          <option value="">{t("fib.log.fields.chooseCategory")}</option>
          {INCOME_CATEGORIES.map((value) => (
            <option key={value} value={value}>
              {t(`fib.categories.income.${value}`)}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="income-employer" className="text-sm font-bold">
          {t("fib.log.fields.employerName")}
        </label>
        <input
          id="income-employer"
          type="text"
          value={employerName}
          maxLength={MAX_EMPLOYER_CHARS}
          onChange={(event) => setEmployerName(event.target.value)}
          disabled={pending}
          className={fieldClass}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="income-date" className="text-sm font-bold">
          {t("fib.log.fields.entryDate")}
        </label>
        <input
          id="income-date"
          type="date"
          value={entryDate}
          max={today()}
          onChange={(event) => setEntryDate(event.target.value)}
          disabled={pending}
          className={fieldClass}
        />
      </div>

      <div className="space-y-1.5">
        <label htmlFor="income-notes" className="text-sm font-bold">
          {t("fib.log.fields.notes")}
        </label>
        <textarea
          id="income-notes"
          value={notes}
          maxLength={MAX_NOTES_CHARS}
          rows={3}
          onChange={(event) => setNotes(event.target.value)}
          disabled={pending}
          className={`${fieldClass} h-auto py-2`}
        />
      </div>

      {shownKey && (
        <p role="alert" className="text-sm text-danger-ink">
          {t(shownKey)}
        </p>
      )}

      <Button type="submit" size="lg" className={submitClass} disabled={pending}>
        {pending ? t("fib.log.submitting") : t("fib.log.submit")}
      </Button>
    </form>
  );
}
