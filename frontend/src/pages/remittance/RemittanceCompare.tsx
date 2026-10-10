import { ArrowLeftRight } from "lucide-react";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "react-router-dom";

import EmptyState from "@/components/common/EmptyState";
import LoadingSpinner from "@/components/common/LoadingSpinner";
import PageHeader from "@/components/common/PageHeader";
import PageStateFrame from "@/components/common/PageStateFrame";
import ComparisonSummary from "@/components/remittance/ComparisonSummary";
import ComparisonTable from "@/components/remittance/ComparisonTable";
import CorridorPicker from "@/components/remittance/CorridorPicker";
import RecommendationCard from "@/components/remittance/RecommendationCard";
import SavingsCallout from "@/components/remittance/SavingsCallout";
import { Skeleton } from "@/components/ui/skeleton";
import PillarIllustration from "@/components/visual/PillarIllustration";
import { useI18n } from "@/hooks/useI18n";
import { useCompareRemittance, useLogTransfer } from "@/hooks/useRemittance";
import { toast } from "@/hooks/useToast";
import { useUserProfile } from "@/hooks/useUser";
import i18n from "@/lib/i18n";
import type { ProviderResult, RemittanceComparison } from "@/types/remittance";
import { compareFailure, defaultCorridor, parseCompareLink } from "@/utils/corridors";
import { errorMessageKey } from "@/utils/errors";

// recharts is a sizeable chunk (D-45): loaded only once a comparison exists to show it for.
const TrendChart = lazy(() => import("@/components/remittance/TrendChart"));

// A new comparison starts the advice card afresh; the same one keeps any advice already written.
function compareKey(comparison: RemittanceComparison): string {
  return `${comparison.corridor_id}/${comparison.send_amount}`;
}

/** What the results column shows while a comparison runs: the same shapes the answer will take. */
function ResultsSkeleton() {
  const { t } = useI18n();
  return (
    <div role="status" aria-live="polite" className="space-y-4">
      <span className="sr-only">{t("common.loading")}</span>
      <Skeleton className="h-52 w-full rounded-2xl" />
      <Skeleton className="h-28 w-full rounded-2xl" />
      <Skeleton className="h-72 w-full rounded-2xl" />
    </div>
  );
}

/** Remittance X-Ray: choose a corridor and an amount, see what the services cost. */
export default function RemittanceCompare() {
  const { t } = useI18n();
  const profile = useUserProfile();
  const compare = useCompareRemittance();
  // A link from the Coach's plan carries the corridor and the amount to compare: the form shows
  // them and the comparison runs once, so the worker lands on the answer.
  const [searchParams] = useSearchParams();
  const link = useMemo(() => parseCompareLink(searchParams), [searchParams]);
  const linkStarted = useRef(false);
  const startComparison = compare.mutate;
  useEffect(() => {
    if (link !== null && !linkStarted.current) {
      linkStarted.current = true;
      startComparison({ corridor_id: link.corridorId, amount: link.amount });
    }
  }, [link, startComparison]);
  const logTransfer = useLogTransfer();
  const [loggedRpwIds, setLoggedRpwIds] = useState<ReadonlySet<number>>(new Set());
  // Tracks which comparison `loggedRpwIds` belongs to, so a new one (new amount or corridor)
  // starts with nothing logged against it, even if some of the same rpw_ids show up again.
  const [loggedFor, setLoggedFor] = useState<RemittanceComparison | null>(null);
  if (compare.data && compare.data !== loggedFor) {
    setLoggedFor(compare.data);
    setLoggedRpwIds(new Set());
  }

  if (profile.isPending) {
    return (
      <PageStateFrame pillar="remit" icon={ArrowLeftRight} title={t("remittance.title")}>
        <LoadingSpinner label={t("common.loading")} className="py-16" />
      </PageStateFrame>
    );
  }

  function handleLog(provider: ProviderResult) {
    const comparison = compare.data;
    if (!comparison) {
      return;
    }
    logTransfer.mutate(
      { comparison, rpwId: provider.rpw_id },
      {
        onSuccess: () => {
          setLoggedRpwIds((current) => new Set(current).add(provider.rpw_id));
          toast({ messageKey: "remittance.table.logAction.toastSuccess" });
        },
        onError: (error) => {
          toast({ messageKey: errorMessageKey(error), variant: "error" });
        },
      }
    );
  }

  const language = i18n.resolvedLanguage ?? "en";
  // Without the profile the form still works; it only starts on the first corridor.
  const initialCorridor =
    link?.corridorId ?? defaultCorridor(profile.data?.host_country, profile.data?.home_country);
  const serverError =
    compare.isError && compare.variables
      ? compareFailure(compare.error, compare.variables.corridor_id, language)
      : null;

  return (
    <div className="space-y-5">
      <PageHeader
        pillar="remit"
        icon={ArrowLeftRight}
        title={t("remittance.title")}
        description={t("remittance.subtitle")}
      />

      <div className="grid items-start gap-5 lg:grid-cols-12">
        <div className="lg:sticky lg:top-24 lg:col-span-5 xl:col-span-4">
          <CorridorPicker
            initialCorridor={initialCorridor}
            initialAmount={link?.amount}
            pending={compare.isPending}
            serverError={serverError}
            onSubmit={(request) => compare.mutate(request)}
          />
        </div>

        <div className="min-w-0 space-y-5 lg:col-span-7 xl:col-span-8">
          {compare.isPending && <ResultsSkeleton />}
          {!compare.isPending && !compare.data && (
            <EmptyState
              icon={ArrowLeftRight}
              title={t("remittance.empty.title")}
              description={t("remittance.empty.description")}
              illustration={<PillarIllustration pillar="remit" />}
              className="min-h-[22rem] justify-center"
            />
          )}
          {compare.data && !compare.isPending && (
            <>
              <ComparisonSummary comparison={compare.data} />
              <RecommendationCard key={compareKey(compare.data)} comparison={compare.data} />
              <SavingsCallout comparison={compare.data} />
              <ComparisonTable
                comparison={compare.data}
                onLog={handleLog}
                pendingRpwId={logTransfer.isPending ? (logTransfer.variables?.rpwId ?? null) : null}
                loggedRpwIds={loggedRpwIds}
              />
              <Suspense fallback={<Skeleton className="h-72 w-full rounded-2xl" />}>
                <TrendChart comparison={compare.data} />
              </Suspense>
            </>
          )}
        </div>
      </div>
    </div>
  );
}
