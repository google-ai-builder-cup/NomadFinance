import { MutationCache, QueryCache, QueryClient } from "@tanstack/react-query";

import { toast } from "@/hooks/useToast";
import { errorMessageKey, isRetryable } from "@/utils/errors";

declare module "@tanstack/react-query" {
  interface Register {
    mutationMeta: {
      /** The component shows this mutation's failure itself, so no global toast. */
      inlineError?: boolean;
    };
  }
}

export const queryClient: QueryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error, query) => {
      // A first load that fails is shown by the page itself, with its own Retry button. A
      // refetch that fails while older data is still on screen would otherwise go unnoticed.
      if (query.state.data === undefined) {
        return;
      }
      toast({
        id: `query-${query.queryHash}`,
        messageKey: errorMessageKey(error),
        variant: "error",
        action: {
          labelKey: "common.retry",
          onClick: () => void queryClient.refetchQueries({ queryKey: query.queryKey, exact: true }),
        },
      });
    },
  }),
  mutationCache: new MutationCache({
    // No Retry button here: repeating a write (a report, an upload) is left to the form's own
    // submit button, so it is always a deliberate choice.
    onError: (error, _variables, _onMutateResult, mutation) => {
      if (mutation.meta?.inlineError === true) {
        return;
      }
      toast({ messageKey: errorMessageKey(error), variant: "error" });
    },
  }),
  defaultOptions: {
    // TanStack Query's default is to pause a request while the browser says it is offline and
    // wait, silently, for the signal to return: a worker who loses signal and taps "Compare"
    // saw "Comparing…" for as long as they were offline, and a page showed its spinner forever
    // (NF-P4-002 Slow-3G run). Sending the request anyway fails it at once with the offline
    // error, which every page already words ("No internet connection") with a way to try again.
    queries: {
      networkMode: "always",
      retry: (failureCount, error) => failureCount < 1 && isRetryable(error),
      staleTime: 60_000,
    },
    mutations: { networkMode: "always" },
  },
});
