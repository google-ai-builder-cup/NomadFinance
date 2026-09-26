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
    queries: {
      retry: (failureCount, error) => failureCount < 1 && isRetryable(error),
      staleTime: 60_000,
    },
  },
});
