import { type FormEvent, useState } from "react";

import BillPhotoPicker from "@/components/fib/BillPhotoPicker";
import { fieldClass } from "@/components/fib/styles";
import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";
import type { BillLogRequest } from "@/types/fib";
import { BILL_CATEGORIES, type BillCategory, MAX_NOTES_CHARS, MAX_VENDOR_CHARS } from "@/types/fib";
import { blankToUndefined, LOGGABLE_CURRENCIES, parseAmount } from "@/utils/fibForm";
import { cn } from "@/lib/utils";

export interface BillFormProps {
  defaultCurrency: string;
  manualPending: boolean;
  manualErrorKey: string | null;
  onSubmitManual: (body: BillLogRequest) => void;
  scanPending: boolean;
  scanErrorKey: string | null;
  onCapture: (file: File) => void;
}

type Mode = "photo" | "manual";

function today(): string {
  return new Date().toISOString().slice(0, 10);
}

/** Bill entry: a photo read by Gemini Vision (`POST /fib/bill/scan`), or typed by hand
 * (`POST /fib/bill`). */
export default function BillForm({
  defaultCurrency,
  manualPending,
  manualErrorKey,
  onSubmitManual,
  scanPending,
  scanErrorKey,
  onCapture,
}: BillFormProps) {
  const { t } = useI18n();
  const [mode, setMode] = useState<Mode>("photo");
  const [photo, setPhoto] = useState<File | null>(null);

  const [amountText, setAmountText] = useState("");
  const [currency, setCurrency] = useState(defaultCurrency);
  const [vendor, setVendor] = useState("");
  const [billDate, setBillDate] = useState("");
  const [paid, setPaid] = useState(false);
  const [category, setCategory] = useState<BillCategory | "">("");
  const [notes, setNotes] = useState("");
  const [entryDate, setEntryDate] = useState(today());
  const [problemKey, setProblemKey] = useState<string | null>(null);

  function handleScan() {
    if (photo) {
      onCapture(photo);
    }
  }

  function handleManualSubmit(event: FormEvent) {
    event.preventDefault();
    if (manualPending) {
      return;
    }
    const amount = parseAmount(amountText, currency);
    if (!amount.ok) {
      setProblemKey(`fib.log.errors.amount.${amount.problem}`);
      return;
    }
    setProblemKey(null);
    onSubmitManual({
      entry_date: entryDate || undefined,
      amount: amount.amount,
      currency,
      vendor: blankToUndefined(vendor),
      bill_date: billDate || undefined,
      paid,
      category: category || undefined,
      notes: blankToUndefined(notes),
    });
  }

  const shownKey = problemKey ?? manualErrorKey;

  return (
    <div className="space-y-4">
      <div
        role="tablist"
        aria-label={t("fib.bill.modeLabel")}
        className="grid grid-cols-2 gap-1 rounded-lg bg-muted p-1"
      >
        {(["photo", "manual"] as const).map((value) => (
          <button
            key={value}
            type="button"
            role="tab"
            aria-selected={mode === value}
            onClick={() => setMode(value)}
            className={cn(
              "rounded-md px-2 py-2 text-sm font-medium transition-colors",
              mode === value
                ? "bg-background shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t(`fib.bill.modes.${value}`)}
          </button>
        ))}
      </div>

      {mode === "photo" ? (
        <div className="space-y-4">
          <BillPhotoPicker
            file={photo}
            onSelect={setPhoto}
            onClear={() => setPhoto(null)}
            disabled={scanPending}
          />
          {scanErrorKey && (
            <p role="alert" className="text-sm text-destructive">
              {t(scanErrorKey)}
            </p>
          )}
          <Button
            type="button"
            size="lg"
            className="h-11 w-full"
            disabled={!photo || scanPending}
            onClick={handleScan}
          >
            {scanPending ? t("fib.bill.scan.submitting") : t("fib.bill.scan.submit")}
          </Button>
        </div>
      ) : (
        <form onSubmit={handleManualSubmit} noValidate className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label htmlFor="bill-amount" className="text-sm font-medium">
                {t("fib.log.fields.amount")}
              </label>
              <input
                id="bill-amount"
                type="text"
                inputMode="decimal"
                value={amountText}
                onChange={(event) => setAmountText(event.target.value)}
                disabled={manualPending}
                className={fieldClass}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="bill-currency" className="text-sm font-medium">
                {t("fib.log.fields.currency")}
              </label>
              <select
                id="bill-currency"
                value={currency}
                onChange={(event) => setCurrency(event.target.value)}
                disabled={manualPending}
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
            <label htmlFor="bill-vendor" className="text-sm font-medium">
              {t("fib.log.fields.vendor")}
            </label>
            <input
              id="bill-vendor"
              type="text"
              value={vendor}
              maxLength={MAX_VENDOR_CHARS}
              onChange={(event) => setVendor(event.target.value)}
              disabled={manualPending}
              className={fieldClass}
            />
          </div>

          <div className="space-y-1.5">
            <label htmlFor="bill-category" className="text-sm font-medium">
              {t("fib.log.fields.category")}
            </label>
            <select
              id="bill-category"
              value={category}
              onChange={(event) => setCategory(event.target.value as BillCategory)}
              disabled={manualPending}
              className={fieldClass}
            >
              <option value="">{t("fib.log.fields.chooseCategory")}</option>
              {BILL_CATEGORIES.map((value) => (
                <option key={value} value={value}>
                  {t(`fib.categories.bill.${value}`)}
                </option>
              ))}
            </select>
          </div>

          <label
            className={cn(
              "flex cursor-pointer items-center gap-3 rounded-lg border p-3 has-[:focus-visible]:ring-1 has-[:focus-visible]:ring-ring",
              paid ? "border-primary bg-accent" : "hover:bg-accent"
            )}
          >
            <input
              type="checkbox"
              checked={paid}
              onChange={(event) => setPaid(event.target.checked)}
              disabled={manualPending}
              className="h-4 w-4 accent-primary"
            />
            <span className="text-sm font-medium">{t("fib.log.fields.paid")}</span>
          </label>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label htmlFor="bill-date" className="text-sm font-medium">
                {t("fib.log.fields.billDate")}
              </label>
              <input
                id="bill-date"
                type="date"
                value={billDate}
                max={today()}
                onChange={(event) => setBillDate(event.target.value)}
                disabled={manualPending}
                className={fieldClass}
              />
            </div>
            <div className="space-y-1.5">
              <label htmlFor="bill-entry-date" className="text-sm font-medium">
                {t("fib.log.fields.entryDate")}
              </label>
              <input
                id="bill-entry-date"
                type="date"
                value={entryDate}
                max={today()}
                onChange={(event) => setEntryDate(event.target.value)}
                disabled={manualPending}
                className={fieldClass}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="bill-notes" className="text-sm font-medium">
              {t("fib.log.fields.notes")}
            </label>
            <textarea
              id="bill-notes"
              value={notes}
              maxLength={MAX_NOTES_CHARS}
              rows={3}
              onChange={(event) => setNotes(event.target.value)}
              disabled={manualPending}
              className={`${fieldClass} h-auto py-2`}
            />
          </div>

          {shownKey && (
            <p role="alert" className="text-sm text-destructive">
              {t(shownKey)}
            </p>
          )}

          <Button type="submit" size="lg" className="h-11 w-full" disabled={manualPending}>
            {manualPending ? t("fib.log.submitting") : t("fib.log.submit")}
          </Button>
        </form>
      )}
    </div>
  );
}
