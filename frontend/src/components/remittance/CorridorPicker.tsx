import { type FormEvent, useState } from "react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { RemittanceCompareRequest } from "@/types/remittance";
import { CORRIDOR_IDS, type CorridorId } from "@/types/enums";
import { CORRIDORS, type AmountProblem, type MessageRef, parseAmount } from "@/utils/corridors";
import { countryName, currencyName, formatMoney } from "@/utils/format";

const fieldClass =
  "h-11 w-full rounded-md border border-input bg-background px-3 text-base shadow-sm " +
  "focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:opacity-50";

export interface CorridorPickerProps {
  /** The corridor selected when the form first shows (the worker's own, from the profile). */
  initialCorridor: CorridorId;
  /** A comparison is running: the form is locked. */
  pending: boolean;
  /** An error from the server, shown above the button. */
  serverError?: MessageRef | null;
  onSubmit: (request: RemittanceCompareRequest) => void;
}

/** Remittance X-Ray's form: where the money goes and how much (NF-P2-018). */
export default function CorridorPicker({
  initialCorridor,
  pending,
  serverError,
  onSubmit,
}: CorridorPickerProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const [corridorId, setCorridorId] = useState<CorridorId>(initialCorridor);
  const [amountText, setAmountText] = useState("");
  const [problem, setProblem] = useState<AmountProblem | null>(null);
  const info = CORRIDORS[corridorId];
  const money = (amount: number) => formatMoney(amount, info.sendCurrency, language, info.decimals);
  const limits = { min: money(info.minAmount), max: money(info.maxAmount) };

  function changeCorridor(next: CorridorId) {
    // 645 SGD means nothing in yen: a new sending currency starts from an empty amount.
    if (CORRIDORS[next].sendCurrency !== info.sendCurrency) {
      setAmountText("");
    }
    setProblem(null);
    setCorridorId(next);
  }

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const check = parseAmount(amountText, info);
    if (!check.ok) {
      setProblem(check.problem);
      return;
    }
    setProblem(null);
    onSubmit({ corridor_id: corridorId, amount: check.amount });
  }

  const problemText =
    problem === null
      ? null
      : problem === "decimals"
        ? info.decimals === 0
          ? t("remittance.form.errors.wholeNumber", { currency: info.sendCurrency })
          : t("remittance.form.errors.decimals", { places: String(info.decimals) })
        : t(`remittance.form.errors.${problem}`, limits);

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6 rounded-lg border bg-card p-6">
      <div className="space-y-1.5">
        <label htmlFor="remittance-corridor" className="text-sm font-medium">
          {t("remittance.form.corridor")}
        </label>
        <select
          id="remittance-corridor"
          value={corridorId}
          onChange={(event) => changeCorridor(event.target.value as CorridorId)}
          disabled={pending}
          className={fieldClass}
        >
          {CORRIDOR_IDS.map((id) => (
            <option key={id} value={id}>
              {countryName(CORRIDORS[id].host, language)} →{" "}
              {countryName(CORRIDORS[id].home, language)}
            </option>
          ))}
        </select>
        <p className="text-xs text-muted-foreground">
          {t("remittance.form.currencies", {
            send: `${currencyName(info.sendCurrency, language)} (${info.sendCurrency})`,
            receive: `${currencyName(info.receiveCurrency, language)} (${info.receiveCurrency})`,
          })}
        </p>
      </div>

      <div className="space-y-1.5">
        <label htmlFor="remittance-amount" className="text-sm font-medium">
          {t("remittance.form.amount")}
        </label>
        <div className="relative">
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 left-3 flex items-center text-sm font-medium text-muted-foreground"
          >
            {info.sendCurrency}
          </span>
          <input
            id="remittance-amount"
            type="text"
            inputMode={info.decimals === 0 ? "numeric" : "decimal"}
            autoComplete="transaction-amount"
            value={amountText}
            onChange={(event) => {
              setAmountText(event.target.value);
              setProblem(null);
            }}
            disabled={pending}
            aria-invalid={problem !== null}
            aria-describedby={cn(
              "remittance-amount-hint",
              problem !== null && "remittance-amount-error"
            )}
            placeholder={String(info.surveyAmounts[1])}
            className={cn(fieldClass, "pl-14", problem !== null && "border-destructive")}
          />
        </div>
        <p id="remittance-amount-hint" className="text-xs text-muted-foreground">
          {t("remittance.form.amountHint", { currency: info.sendCurrency, ...limits })}
        </p>
        {problemText && (
          <p id="remittance-amount-error" role="alert" className="text-sm text-destructive">
            {problemText}
          </p>
        )}
      </div>

      <div role="group" aria-labelledby="remittance-shortcuts" className="space-y-2">
        <p id="remittance-shortcuts" className="text-xs text-muted-foreground">
          {t("remittance.form.shortcuts")}
        </p>
        <div className="flex flex-wrap gap-2">
          {info.surveyAmounts.map((amount) => (
            <Button
              key={amount}
              type="button"
              variant="outline"
              className="h-10 px-4"
              disabled={pending}
              aria-pressed={amountText === String(amount)}
              onClick={() => {
                setAmountText(String(amount));
                setProblem(null);
              }}
            >
              {money(amount)}
            </Button>
          ))}
        </div>
      </div>

      {serverError && (
        <p role="alert" className="text-sm text-destructive">
          {t(serverError.key, serverError.values)}
        </p>
      )}

      <Button type="submit" size="lg" className="h-11 w-full" disabled={pending}>
        {pending ? t("remittance.form.submitting") : t("remittance.form.submit")}
      </Button>
    </form>
  );
}
