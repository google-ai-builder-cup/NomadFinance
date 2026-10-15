import { ApiError } from "@/services/apiClient";
import { readTypedAmount } from "@/utils/amountReading";
import { CORRIDOR_IDS, type CorridorId, type HomeCountry, type HostCountry } from "@/types/enums";
import { errorMessageKey } from "@/utils/errors";
import { requestFailureKey } from "@/utils/pipelineProgress";
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
 * Read what the worker typed. Accepts "645", "645.50" and "645,50", and thousands grouped with
 * commas ("6,450", "1,530.50") or dots ("1.530,50"); a dot before exactly three digits ("6.450")
 * is a decimal point. For the yen, every separator is a thousands separator. How the marks are
 * read is in `readTypedAmount`.
 */
export function parseAmount(text: string, info: CorridorInfo): AmountCheck {
  const typed = readTypedAmount(text, info.decimals === 0);
  if (!typed.ok) {
    return text.trim() === "" ? { ok: false, problem: "empty" } : typed;
  }
  const normalized = typed.normalized;
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

/**
 * What to tell the worker when the written advice could not be made. The wording of the contract
 * pipeline's "Something went wrong while checking your contract" is for a contract: a 502 here
 * (the model's answer was unusable) says the server had a problem instead, and a busy or slow
 * model keeps the shared words.
 */
export function adviceFailureKey(error: unknown): string {
  if (error instanceof ApiError && error.status === 502) {
    return "errors.server";
  }
  return requestFailureKey(error);
}

/** A link into Remittance X-Ray (`/remittance?corridor=SG-PH&amount=400`), such as the 90-day plan
 * gives: the corridor and amount to fill in, or null when either is missing or not valid for it.
 * A bad value never fills the form with something the worker did not choose. */
export function parseCompareLink(params: URLSearchParams): {
  corridorId: CorridorId;
  amount: number;
} | null {
  const corridor = params.get("corridor");
  const raw = params.get("amount");
  if (
    corridor === null ||
    raw === null ||
    !(CORRIDOR_IDS as readonly string[]).includes(corridor)
  ) {
    return null;
  }
  const corridorId = corridor as CorridorId;
  const check = parseAmount(raw, CORRIDORS[corridorId]);
  return check.ok ? { corridorId, amount: check.amount } : null;
}
