import { useState } from "react";
import { Link } from "react-router-dom";

import BillForm from "@/components/fib/BillForm";
import IncomeForm from "@/components/fib/IncomeForm";
import SavingsForm from "@/components/fib/SavingsForm";
import { Button } from "@/components/ui/button";
import { useLogBill, useLogIncome, useLogSavings, useScanBill } from "@/hooks/useFIB";
import { useI18n } from "@/hooks/useI18n";
import { toast } from "@/hooks/useToast";
import { useUserProfile } from "@/hooks/useUser";
import { cn } from "@/lib/utils";
import { errorMessageKey } from "@/utils/errors";
import { HOST_CURRENCY, scanFailureKey } from "@/utils/fibForm";

const TABS = ["income", "transfer", "bill", "savings"] as const;
type Tab = (typeof TABS)[number];

/** Tabs for the four kinds of activity the Financial Identity Builder tracks (NF-P3-016). */
export default function ActivityLogger() {
  const { t } = useI18n();
  const profile = useUserProfile();
  const [tab, setTab] = useState<Tab>("income");
  // Bumped after a successful log to remount the active form with a clean draft.
  const [resetCount, setResetCount] = useState(0);

  const logIncome = useLogIncome();
  const logBill = useLogBill();
  const scanBill = useScanBill();
  const logSavings = useLogSavings();

  const currency = HOST_CURRENCY[profile.data?.host_country ?? "SG"];

  function logged() {
    toast({ messageKey: "fib.log.success" });
    setResetCount((count) => count + 1);
  }

  return (
    <div className="card-surface space-y-6 p-5 md:p-7">
      <div
        role="tablist"
        aria-label={t("fib.log.tabsLabel")}
        className="grid grid-cols-4 gap-1 rounded-xl bg-muted p-1"
      >
        {TABS.map((name) => (
          <button
            key={name}
            type="button"
            role="tab"
            aria-selected={tab === name}
            onClick={() => setTab(name)}
            className={cn(
              "min-h-11 rounded-lg px-1 py-2 text-xs font-bold transition-all duration-base sm:text-sm",
              tab === name
                ? "bg-card text-identity-ink shadow-sm"
                : "text-muted-foreground hover:text-foreground"
            )}
          >
            {t(`fib.log.tabs.${name}`)}
          </button>
        ))}
      </div>

      {tab === "income" && (
        <IncomeForm
          key={`income-${resetCount}`}
          defaultCurrency={currency}
          pending={logIncome.isPending}
          errorKey={logIncome.isError ? errorMessageKey(logIncome.error) : null}
          onSubmit={(body) => logIncome.mutate(body, { onSuccess: logged })}
        />
      )}

      {tab === "bill" && (
        <BillForm
          key={`bill-${resetCount}`}
          defaultCurrency={currency}
          manualPending={logBill.isPending}
          manualErrorKey={logBill.isError ? errorMessageKey(logBill.error) : null}
          onSubmitManual={(body) => logBill.mutate(body, { onSuccess: logged })}
          scanPending={scanBill.isPending}
          scanErrorKey={scanBill.isError ? scanFailureKey(scanBill.error) : null}
          onCapture={(file) => scanBill.mutate(file, { onSuccess: logged })}
        />
      )}

      {tab === "savings" && (
        <SavingsForm
          key={`savings-${resetCount}`}
          defaultCurrency={currency}
          pending={logSavings.isPending}
          errorKey={logSavings.isError ? errorMessageKey(logSavings.error) : null}
          onSubmit={(body) => logSavings.mutate(body, { onSuccess: logged })}
        />
      )}

      {tab === "transfer" && (
        <div className="space-y-4 rounded-2xl bg-remit-tint p-6 text-center">
          <p className="text-sm text-muted-foreground">{t("fib.log.transfer.explainer")}</p>
          <Button
            asChild
            size="lg"
            className="h-12 w-full rounded-xl bg-remit-deep text-base font-bold text-white hover:bg-remit-deep/90"
          >
            <Link to="/remittance">{t("fib.log.transfer.cta")}</Link>
          </Button>
        </div>
      )}
    </div>
  );
}
