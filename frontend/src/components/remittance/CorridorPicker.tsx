import { ArrowRight } from "lucide-react";
import { type FormEvent, useState } from "react";

import AmountReading from "@/components/common/AmountReading";
import CountryPair from "@/components/common/CountryPair";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import i18n from "@/lib/i18n";
import { cn } from "@/lib/utils";
import type { RemittanceCompareRequest } from "@/types/remittance";
import { CORRIDOR_IDS, type CorridorId } from "@/types/enums";
import { CORRIDORS, type AmountProblem, type MessageRef, parseAmount } from "@/utils/corridors";
import { countryName, currencyName, formatMoney } from "@/utils/format";

const fieldClass =
  "h-12 w-full rounded-xl border border-input bg-card px-3 text-base font-semibold shadow-sm " +
  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-50";

export interface CorridorPickerProps {
  /** The corridor selected when the form first shows (the worker's own, from the profile). */
  initialCorridor: CorridorId;
  /** The amount filled in when the form first shows (from a link, such as the Coach plan's). */
  initialAmount?: number;
  /** A comparison is running: the form is locked. */
  pending: boolean;
  /** An error from the server, shown above the button. */
  serverError?: MessageRef | null;
  onSubmit: (request: RemittanceCompareRequest) => void;
}

/** Remittance X-Ray's form: where the money goes and how much (NF-P2-018). The corridor is a
 * set of six pair cards (a radio group), not a drop-down, so every option is visible at once. */
export default function CorridorPicker({
  initialCorridor,
  initialAmount,
  pending,
  serverError,
  onSubmit,
}: CorridorPickerProps) {
  const { t } = useI18n();
  const language = i18n.resolvedLanguage ?? "en";
  const [corridorId, setCorridorId] = useState<CorridorId>(initialCorridor);
  const [amountText, setAmountText] = useState(
    initialAmount === undefined ? "" : String(initialAmount)
  );
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
    <form onSubmit={handleSubmit} noValidate className="card-surface space-y-6 p-5 md:p-6">
      <fieldset className="space-y-2.5" disabled={pending}>
        <legend className="text-sm font-bold">{t("remittance.form.corridor")}</legend>
        <div
          role="radiogroup"
          aria-label={t("remittance.form.corridor")}
          className="grid grid-cols-2 gap-2.5"
        >
          {CORRIDOR_IDS.map((id) => {
            const corridor = CORRIDORS[id];
            const selected = id === corridorId;
            return (
              <button
                key={id}
                type="button"
                role="radio"
                aria-checked={selected}
                onClick={() => changeCorridor(id)}
                className={cn(
                  "flex min-h-[3.75rem] items-center gap-2.5 rounded-xl border bg-card px-3 py-2 text-left transition-all duration-base",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60",
                  selected
                    ? "border-remit bg-remit-tint shadow-sm ring-2 ring-remit/25"
                    : "hover:border-remit/50 hover:bg-accent"
                )}
              >
                <CountryPair host={corridor.host} home={corridor.home} />
                <span className="min-w-0">
                  <span className="flex items-center gap-1 text-sm font-bold">
                    {corridor.host}
                    <ArrowRight className="h-3 w-3 text-muted-foreground" aria-hidden="true" />
                    {corridor.home}
                  </span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {corridor.sendCurrency}→{corridor.receiveCurrency}
                  </span>
                </span>
                <span className="sr-only">
                  {countryName(corridor.host, language)} → {countryName(corridor.home, language)}
                </span>
              </button>
            );
          })}
        </div>
        <p className="text-xs text-muted-foreground">
          {t("remittance.form.currencies", {
            send: `${currencyName(info.sendCurrency, language)} (${info.sendCurrency})`,
            receive: `${currencyName(info.receiveCurrency, language)} (${info.receiveCurrency})`,
          })}
        </p>
      </fieldset>

      <div className="space-y-1.5">
        <label htmlFor="remittance-amount" className="text-sm font-bold">
          {t("remittance.form.amount")}
        </label>
        <div className="relative">
          <span
            aria-hidden="true"
            className="pointer-events-none absolute inset-y-0 left-3.5 flex items-center text-sm font-bold text-muted-foreground"
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
            className={cn(
              fieldClass,
              "pl-16 tabular-nums",
              problem !== null && "border-destructive"
            )}
          />
        </div>
        <p id="remittance-amount-hint" className="text-xs text-muted-foreground">
          {t("remittance.form.amountHint", { currency: info.sendCurrency, ...limits })}
        </p>
        <AmountReading text={amountText} currency={info.sendCurrency} decimals={info.decimals} />
        {problemText && (
          <p
            id="remittance-amount-error"
            role="alert"
            className="text-sm font-medium text-danger-ink"
          >
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
              className={cn(
                "h-11 rounded-xl bg-card px-4 font-bold tabular-nums",
                amountText === String(amount) && "border-remit bg-remit-tint"
              )}
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
        <p role="alert" className="text-sm font-medium text-danger-ink">
          {t(serverError.key, serverError.values)}
        </p>
      )}

      <Button
        type="submit"
        size="lg"
        className="h-12 w-full rounded-xl bg-remit-deep text-base font-bold text-white hover:bg-remit-deep/90"
        disabled={pending}
      >
        {pending ? t("remittance.form.submitting") : t("remittance.form.submit")}
      </Button>
    </form>
  );
}
