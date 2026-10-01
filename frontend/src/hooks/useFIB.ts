import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { useAuth } from "@/hooks/useAuth";
import {
  exportReport,
  getFinancialProfile,
  getLatestReport,
  listBillEntries,
  listIncomeEntries,
  listSavingsEntries,
  logBill,
  logIncome,
  logSavings,
  scanBill,
} from "@/services/fibService";
import type { BillEntry, IncomeEntry, SavingsEntry } from "@/types/fib";
import { monthWindow } from "@/utils/fibTimeline";

// The dashboard's chart and category breakdowns cover the same trailing window the weekly
// recompute itself uses (profile_builder.py: "the current month and the 11 before it").
const WINDOW_MONTHS = 12;

function financialProfileKey(uid: string | undefined) {
  return ["financialProfile", uid] as const;
}

/** Exported so the log mutations below can refetch it the moment an entry is stored. */
export function financialTimelineKey(uid: string | undefined) {
  return ["fibTimeline", uid] as const;
}

export interface FinancialTimelineData {
  income: IncomeEntry[];
  bills: BillEntry[];
  savings: SavingsEntry[];
}

/** The signed-in worker's computed Financial Identity profile; `data` is null before the
 * weekly cron has ever found them enough activity to score (NF-P3-013). */
export function useFinancialProfile() {
  const { user } = useAuth();
  const uid = user?.uid;
  return useQuery({
    queryKey: financialProfileKey(uid),
    queryFn: () => getFinancialProfile(uid ?? ""),
    enabled: uid !== undefined,
    // Only the weekly cron writes this; no need to refetch on every window focus.
    staleTime: 5 * 60_000,
  });
}

/**
 * Income, bill and savings entries for the trailing 12 months, for the timeline chart and
 * category breakdowns (NF-P3-017). Read live from Firestore, not the weekly-stale profile
 * (fib.md: "Timeline queries use a date range on `entry_date`").
 */
export function useFinancialTimeline() {
  const { user } = useAuth();
  const uid = user?.uid;
  return useQuery({
    queryKey: financialTimelineKey(uid),
    queryFn: async (): Promise<FinancialTimelineData> => {
      const since = `${monthWindow(WINDOW_MONTHS, new Date())[0]}-01`;
      const [income, bills, savings] = await Promise.all([
        listIncomeEntries(uid ?? "", since),
        listBillEntries(uid ?? "", since),
        listSavingsEntries(uid ?? "", since),
      ]);
      return { income, bills, savings };
    },
    enabled: uid !== undefined,
  });
}

/**
 * Shared options for the four log mutations below. Each stores an entry the moment it
 * succeeds, so a retry on the same mutation would double-log it: the worker starts a fresh
 * one instead. The form shows the error next to its own submit button, same as the radar
 * report form. On success, the timeline query is refetched so the dashboard (NF-P3-017) shows
 * the new entry as soon as the worker navigates back to it — the same pattern `useUser.ts`
 * already uses for profile writes, not a live Firestore listener.
 */
function useLogMutationOptions() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const uid = user?.uid;
  return {
    retry: false,
    meta: { inlineError: true },
    onSuccess: () => queryClient.refetchQueries({ queryKey: financialTimelineKey(uid) }),
  } as const;
}

export function useLogIncome() {
  return useMutation({ mutationFn: logIncome, ...useLogMutationOptions() });
}

export function useLogBill() {
  return useMutation({ mutationFn: logBill, ...useLogMutationOptions() });
}

export function useScanBill() {
  return useMutation({ mutationFn: scanBill, ...useLogMutationOptions() });
}

export function useLogSavings() {
  return useMutation({ mutationFn: logSavings, ...useLogMutationOptions() });
}

function latestReportKey(uid: string | undefined) {
  return ["fibLatestReport", uid] as const;
}

/**
 * A fresh link to the worker's last exported PDF (NF-P3-018); `data` is `undefined` (via the
 * 404 this query does not retry) when nothing has been exported yet, not an error page. A
 * short `staleTime` means returning to the export page re-signs the link rather than handing
 * back one that may already be close to `expires_at`.
 */
export function useLatestReport() {
  const { user } = useAuth();
  const uid = user?.uid;
  return useQuery({
    queryKey: latestReportKey(uid),
    queryFn: getLatestReport,
    enabled: uid !== undefined,
    staleTime: 0,
  });
}

/** Render a new PDF of the current profile, replacing any previous export (NF-P3-018). */
export function useExportReport() {
  const { user } = useAuth();
  const queryClient = useQueryClient();
  const uid = user?.uid;
  return useMutation({
    mutationFn: exportReport,
    retry: false,
    meta: { inlineError: true },
    onSuccess: (result) => queryClient.setQueryData(latestReportKey(uid), result),
  });
}
