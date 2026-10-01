import { useMutation } from "@tanstack/react-query";

import { logBill, logIncome, logSavings, scanBill } from "@/services/fibService";

// Each of these stores an entry the moment it succeeds, so a retry on the same mutation
// would double-log it: the worker starts a fresh one instead. The form shows the error
// next to its own submit button, same as the radar report form.
const LOG_MUTATION_OPTIONS = { retry: false, meta: { inlineError: true } } as const;

export function useLogIncome() {
  return useMutation({ mutationFn: logIncome, ...LOG_MUTATION_OPTIONS });
}

export function useLogBill() {
  return useMutation({ mutationFn: logBill, ...LOG_MUTATION_OPTIONS });
}

export function useScanBill() {
  return useMutation({ mutationFn: scanBill, ...LOG_MUTATION_OPTIONS });
}

export function useLogSavings() {
  return useMutation({ mutationFn: logSavings, ...LOG_MUTATION_OPTIONS });
}
