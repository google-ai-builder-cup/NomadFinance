import type { ProviderResult } from "@/types/remittance";

export type SortColumn = "provider" | "speed" | "fee" | "totalCost" | "receives";
export type SortDirection = "asc" | "desc";

export interface SortState {
  column: SortColumn;
  direction: SortDirection;
}

// The direction each column sorts toward on its first click: the "best first" reading, not
// always ascending (a lower fee is better, but a higher amount received is).
const DEFAULT_DIRECTION: Record<SortColumn, SortDirection> = {
  provider: "asc",
  speed: "asc",
  fee: "asc",
  totalCost: "asc",
  receives: "desc",
};

/** The state after clicking `column`'s header: its own default first, then flips each click. */
export function nextSortState(current: SortState, column: SortColumn): SortState {
  if (current.column === column) {
    return { column, direction: current.direction === "asc" ? "desc" : "asc" };
  }
  return { column, direction: DEFAULT_DIRECTION[column] };
}

function sortValue(provider: ProviderResult, column: SortColumn): number | string {
  switch (column) {
    case "provider":
      return provider.firm.toLocaleLowerCase();
    case "speed":
      return provider.speed_order;
    case "fee":
      return provider.fee;
    case "totalCost":
      return provider.total_cost_pct;
    case "receives":
      // Only reached for comparable providers (see `sortProviders`), so always a number.
      return provider.recipient_receives ?? 0;
  }
}

/**
 * Comparable providers sorted by the chosen column, first first; providers that cannot be
 * compared (paid in another currency) always come last, in the order `/compare` already gave
 * them — the same guarantee the API makes (docs/pipelines/remittance-xray.md).
 */
export function sortProviders(providers: ProviderResult[], sort: SortState): ProviderResult[] {
  const comparable = providers.filter((provider) => provider.comparable);
  const notComparable = providers.filter((provider) => !provider.comparable);

  const sorted = [...comparable].sort((a, b) => {
    const left = sortValue(a, sort.column);
    const right = sortValue(b, sort.column);
    // Tied on the sorted column: always the same order, whichever direction is asked for, so
    // flipping a column's direction twice never reshuffles rows that were never reordered.
    if (left === right) {
      return a.rpw_id - b.rpw_id;
    }
    const cmp = left < right ? -1 : 1;
    return sort.direction === "asc" ? cmp : -cmp;
  });

  return [...sorted, ...notComparable];
}
