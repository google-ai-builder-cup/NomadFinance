import { useId, useState, type FormEvent, type ReactNode } from "react";

import QuickReplyChips from "@/components/common/QuickReplyChips";
import { FIELD_CLASS } from "@/components/coach/fieldClasses";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import {
  isDependents,
  isRate,
  parseAmount,
  plainNumber,
  type InterestPeriod,
} from "@/utils/coachInput";

export interface FieldProps {
  busy: boolean;
  onSend: (text: string) => void;
}

interface FormProps extends FieldProps {
  /** Keeps the form from sending when the value is not usable; shows the error. */
  accept: () => string | null;
  invalid: boolean;
  errorId: string;
  errorText: string;
  children: ReactNode;
}

function Form({ busy, onSend, accept, invalid, errorId, errorText, children }: FormProps) {
  const { t } = useI18n("coach");
  function submit(event: FormEvent) {
    event.preventDefault();
    const text = busy ? null : accept();
    if (text !== null) {
      onSend(text);
    }
  }
  return (
    <form onSubmit={submit} noValidate className="space-y-2">
      {children}
      {invalid && (
        <p id={errorId} role="alert" className="text-sm font-semibold text-danger-ink">
          {errorText}
        </p>
      )}
      <Button type="submit" size="lg" className="min-h-11 w-full" disabled={busy}>
        {t("input.send")}
      </Button>
    </form>
  );
}

/** How many people depend on the worker: a whole number from 0 to 20. */
export function CountField({ busy, onSend }: FieldProps) {
  const { t } = useI18n("coach");
  const id = useId();
  const [value, setValue] = useState("");
  const [invalid, setInvalid] = useState(false);

  function accept() {
    const count = /^\d{1,2}$/.test(value.trim()) ? parseAmount(value) : null;
    setInvalid(!isDependents(count));
    if (count === null || !isDependents(count)) {
      return null;
    }
    setValue("");
    return plainNumber(count);
  }

  return (
    <Form
      busy={busy}
      onSend={onSend}
      accept={accept}
      invalid={invalid}
      errorId={`${id}-error`}
      errorText={t("input.error.count")}
    >
      <label htmlFor={`${id}-count`} className="sr-only">
        {t("input.countLabel")}
      </label>
      <input
        id={`${id}-count`}
        value={value}
        onChange={(event) => setValue(event.target.value)}
        inputMode="numeric"
        autoComplete="off"
        enterKeyHint="send"
        placeholder={t("input.countLabel")}
        aria-invalid={invalid}
        aria-describedby={invalid ? `${id}-error` : undefined}
        className={FIELD_CLASS}
      />
    </Form>
  );
}

const INTEREST_PERIODS: readonly InterestPeriod[] = ["month", "year"];

/** What a debt costs: a percentage for a month or for a year. 0 is allowed (a loan from family). */
export function InterestField({ busy, onSend }: FieldProps) {
  const { t } = useI18n("coach");
  const id = useId();
  const [rate, setRate] = useState("");
  const [period, setPeriod] = useState<InterestPeriod>("month");
  const [invalid, setInvalid] = useState(false);

  function accept() {
    const value = parseAmount(rate);
    setInvalid(!isRate(value));
    if (value === null || !isRate(value)) {
      return null;
    }
    setRate("");
    return t(`input.compose.interest.${period}`, { rate: plainNumber(value) });
  }

  return (
    <Form
      busy={busy}
      onSend={onSend}
      accept={accept}
      invalid={invalid}
      errorId={`${id}-error`}
      errorText={t("input.error.rate")}
    >
      <label htmlFor={`${id}-rate`} className="sr-only">
        {t("input.rateLabel")}
      </label>
      <input
        id={`${id}-rate`}
        value={rate}
        onChange={(event) => setRate(event.target.value)}
        inputMode="decimal"
        autoComplete="off"
        enterKeyHint="send"
        placeholder={t("input.rateLabel")}
        aria-invalid={invalid}
        aria-describedby={invalid ? `${id}-error` : undefined}
        className={FIELD_CLASS}
      />
      <QuickReplyChips
        groupLabel={t("input.periodLabel")}
        options={INTEREST_PERIODS.map((value) => ({
          id: value,
          label: t(`input.period.${value}`),
        }))}
        selectedId={period}
        onSelect={(option) => setPeriod(option.id as InterestPeriod)}
      />
    </Form>
  );
}

const ISO_DATE = /^\d{4}-\d{2}-\d{2}$/;

/** The day of leaving, or "I do not know yet" (the one slot the interview lets a worker skip). */
export function DateField({ busy, onSend }: FieldProps) {
  const { t } = useI18n("coach");
  const id = useId();
  const [day, setDay] = useState("");
  const [invalid, setInvalid] = useState(false);

  function accept() {
    const ok = ISO_DATE.test(day);
    setInvalid(!ok);
    if (!ok) {
      return null;
    }
    setDay("");
    // The date as written in the contract, not in words: the server compares it with the answer.
    return day;
  }

  return (
    <Form
      busy={busy}
      onSend={onSend}
      accept={accept}
      invalid={invalid}
      errorId={`${id}-error`}
      errorText={t("input.error.date")}
    >
      <QuickReplyChips
        groupLabel={t("input.suggestions")}
        options={[{ id: "unknown", label: t("input.dateUnknown") }]}
        disabled={busy}
        onSelect={(option) => onSend(option.label)}
      />
      <label htmlFor={`${id}-date`} className="sr-only">
        {t("input.dateLabel")}
      </label>
      <input
        id={`${id}-date`}
        type="date"
        value={day}
        onChange={(event) => setDay(event.target.value)}
        aria-invalid={invalid}
        aria-describedby={invalid ? `${id}-error` : undefined}
        className={FIELD_CLASS}
      />
    </Form>
  );
}
