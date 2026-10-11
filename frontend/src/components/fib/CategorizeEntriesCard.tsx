import { Tags } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useCategorizeEntries } from "@/hooks/useFIB";
import { useI18n } from "@/hooks/useI18n";
import type { BillEntry } from "@/types/fib";
import { pendingBillCount } from "@/utils/pendingCategories";
import { requestFailureKey } from "@/utils/pipelineProgress";

export interface CategorizeEntriesCardProps {
  bills: readonly BillEntry[];
}

/**
 * "Sort my bills": the screen for `POST /fib/categorize` (NF-P3-012). Shown only while some
 * bill has no category or only a photo's guess; renders nothing otherwise.
 */
export default function CategorizeEntriesCard({ bills }: CategorizeEntriesCardProps) {
  const { t } = useI18n();
  const categorize = useCategorizeEntries();
  const pending = pendingBillCount(bills);
  const result = categorize.data;

  if (pending === 0 && !result) {
    return null;
  }

  return (
    <section
      aria-labelledby="fib-categorize-title"
      className="card-surface space-y-3 border-identity/40 bg-identity-tint p-5"
    >
      <h2 id="fib-categorize-title" className="flex items-center gap-2 font-bold">
        <Tags className="h-4 w-4 text-identity-ink" aria-hidden="true" />
        {t("fib.categorize.title")}
      </h2>
      {result ? (
        <p className="text-sm" aria-live="polite">
          {t("fib.categorize.done", {
            sorted: String(result.categorized.length),
            left: String(result.skipped + result.remaining),
          })}
        </p>
      ) : (
        <p className="text-sm text-muted-foreground">
          {t("fib.categorize.pending", { number: String(pending) })}
        </p>
      )}
      {categorize.isError && (
        <p role="alert" className="text-sm text-danger-ink">
          {t(requestFailureKey(categorize.error))}
        </p>
      )}
      {pending > 0 && (
        <Button
          size="sm"
          className="h-10 rounded-lg bg-identity-deep px-4 font-bold text-white hover:bg-identity-deep/90"
          onClick={() => categorize.mutate()}
          disabled={categorize.isPending}
        >
          {categorize.isPending ? t("fib.categorize.working") : t("fib.categorize.action")}
        </Button>
      )}
    </section>
  );
}
