import { ApiError } from "@/services/apiClient";
import { CORRIDOR_IDS, type CorridorId, type HomeCountry, type HostCountry } from "@/types/enums";
import { errorMessageKey } from "@/utils/errors";
import { formatMoney } from "@/utils/format";

export interface CorridorInfo {
  id: CorridorId;
  host: HostCountry;
  home: HomeCountry;
  sendCurrency: string;
  receiveCurrency: string;
  /** The two amounts the World Bank priced (about USD 200 and 500): exact prices there. */
  surveyAmounts: readonly [number, number];
  /** What `POST /remittance/compare` accepts: a quarter of the smaller survey amount … */
  minAmount: number;
  /** … to ten times the larger one (backend `engine.MIN_AMOUNT_FACTOR`, `MAX_AMOUNT_FACTOR`). */
  maxAmount: number;
  /** Decimal places the sending currency uses; the yen has none. */
  decimals: number;
  /** Decimal places shown for received amounts: none for the rupiah (thousands per unit). */
  receiveDecimals: number;
}

// From the survey file the backend compares with (data-scripts/data/processed/
// rpw_corridors.json, World Bank 2025 Q1). corridors.test.ts recomputes every number from that
// file, so a new survey quarter that changes them fails the test until this table follows.
export const CORRIDORS: Readonly<Record<CorridorId, CorridorInfo>> = {
  "SG-PH": corridor("SG-PH", "SGD", "PHP", [260, 645], 2),
  "SG-IN": corridor("SG-IN", "SGD", "INR", [260, 645], 2),
  "AU-IN": corridor("AU-IN", "AUD", "INR", [200, 500], 2),
  "MY-ID": corridor("MY-ID", "MYR", "IDR", [610, 1530], 2),
  "JP-PH": corridor("JP-PH", "JPY", "PHP", [17000, 42000], 0),
  "AU-PH": corridor("AU-PH", "AUD", "PHP", [200, 500], 2),
};

function corridor(
  id: CorridorId,
  sendCurrency: string,
  receiveCurrency: string,
  surveyAmounts: readonly [number, number],
  decimals: number
): CorridorInfo {
  const [host, home] = id.split("-") as [HostCountry, HomeCountry];
  return {
    id,
    host,
    home,
    sendCurrency,
    receiveCurrency,
    surveyAmounts,
    minAmount: surveyAmounts[0] * 0.25,
    maxAmount: surveyAmounts[1] * 10,
    decimals,
    receiveDecimals: receiveCurrency === "IDR" ? 0 : 2,
  };
}

/**
 * The corridor to show first: the worker's own (host → home) when it is one of the six, else
 * the first from their host country, else the first of all.
 */
export function defaultCorridor(host?: HostCountry, home?: HomeCountry): CorridorId {
  const own = `${host ?? ""}-${home ?? ""}`;
  return (
    CORRIDOR_IDS.find((id) => id === own) ??
    CORRIDOR_IDS.find((id) => CORRIDORS[id].host === host) ??
    CORRIDOR_IDS[0]
  );
}

export type AmountProblem = "empty" | "invalid" | "decimals" | "tooSmall" | "tooLarge";

export type AmountCheck = { ok: true; amount: number } | { ok: false; problem: AmountProblem };

/**
 * Read what the worker typed. Accepts "645", "645.50", "645,50" and grouped thousands in
 * either style ("6,450", "6.450", "1,530.50", "1.530,50"); for the yen, every separator is a
 * thousands separator.
 */
export function parseAmount(text: string, info: CorridorInfo): AmountCheck {
  // \s also covers the no-break space some keyboards put in grouped numbers.
  const raw = text.replace(/[\s']/g, "");
  if (raw === "") {
    return { ok: false, problem: "empty" };
  }
  let normalized: string;
  if (info.decimals === 0 && /^\d+([.,]\d{3})*$/.test(raw)) {
    normalized = raw.replace(/[.,]/g, "");
  } else if (/^\d{1,3}(,\d{3})+(\.\d+)?$/.test(raw)) {
    normalized = raw.replace(/,/g, "");
  } else if (/^\d{1,3}(\.\d{3})+(,\d+)?$/.test(raw)) {
    normalized = raw.replace(/\./g, "").replace(",", ".");
  } else if (/^\d+([.,]\d+)?$/.test(raw)) {
    normalized = raw.replace(",", ".");
  } else {
    return { ok: false, problem: "invalid" };
  }
  const fraction = normalized.split(".")[1] ?? "";
  if (fraction.length > info.decimals) {
    return { ok: false, problem: "decimals" };
  }
  const amount = Number(normalized);
  if (!Number.isFinite(amount) || amount <= 0) {
    return { ok: false, problem: "invalid" };
  }
  if (amount < info.minAmount) {
    return { ok: false, problem: "tooSmall" };
  }
  if (amount > info.maxAmount) {
    return { ok: false, problem: "tooLarge" };
  }
  return { ok: true, amount };
}

export interface MessageRef {
  key: string;
  values?: Record<string, string>;
}

/**
 * What to tell the worker when `POST /remittance/compare` failed. The backend's own text is
 * English only (D-10), so 404 and 422 get translated messages; the 422 names the limits.
 */
export function compareFailure(
  error: unknown,
  corridorId: CorridorId,
  language: string
): MessageRef {
  if (error instanceof ApiError && error.status === 404) {
    return { key: "remittance.form.errors.notLoaded" };
  }
  if (error instanceof ApiError && error.status === 422) {
    const info = CORRIDORS[corridorId];
    const money = (amount: number) =>
      formatMoney(amount, info.sendCurrency, language, info.decimals);
    return {
      key: "remittance.form.errors.outOfRange",
      values: { min: money(info.minAmount), max: money(info.maxAmount) },
    };
  }
  return { key: errorMessageKey(error) };
}
