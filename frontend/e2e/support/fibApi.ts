import type { Page } from "@playwright/test";

import type { TestUser } from "./emulators";
import { type FirestoreValue, setDocument, updateDocument } from "./firestoreRest";

// The Financial Identity backend for the browser tests (NF-HR-004). The log forms post to the API
// and the dashboard reads the entries and the profile from Firestore, so this answers the calls
// and writes the same documents the backend writes (docs/data-model/collections/fib.md).

export interface FibCall {
  method: string;
  path: string;
  body: unknown;
}

export type ScanOutcome = "bill" | "not_a_bill" | "unreadable";

export interface FakeFib {
  calls: FibCall[];
  /** What the bill reader makes of the next photo. */
  scanWill(outcome: ScanOutcome): void;
  to(method: string, pattern: RegExp): FibCall[];
}

type Fields = { [key: string]: FirestoreValue };

const today = () => new Date().toISOString().slice(0, 10);

/** A profile like the weekly job writes for a worker with a few months of activity. */
export async function seedFinancialProfile(user: TestUser, language = "en"): Promise<void> {
  const metric = (score: number) => ({ score, detail: {} });
  await setDocument(`users/${user.uid}/financial_profile/current`, {
    reporting_currency: "SGD",
    period_start: "2026-05-01",
    period_end: today(),
    months_of_data: 5,
    entry_counts: { income: 5, transfers: 4, bills: 9, savings: 3 },
    metrics: {
      income_stability: metric(72),
      savings_rate: metric(48),
      remittance_consistency: metric(100),
      bill_payment_reliability: metric(92),
    },
    overall_score: 78,
    narrative: {
      language,
      text: "Income has been steady and bills are paid on time.",
      model: "stand-in",
    },
    computed_at: new Date(),
  });
}

export async function fibApi(page: Page, user: TestUser): Promise<FakeFib> {
  const calls: FibCall[] = [];
  let scan: ScanOutcome = "bill";
  let exported: { created_at: string } | null = null;
  const uncategorized: string[] = [];
  let count = 0;
  const entry = (kind: "income" | "bills" | "savings", id: string, data: Fields) =>
    setDocument(`users/${user.uid}/${kind}/${id}`, {
      source: "manual",
      ...data,
      created_at: new Date(),
      schema_version: 1,
    });

  await page.route("**/api/v1/fib/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const raw = request.postData() ?? "";
    const isJson = (request.headers()["content-type"] ?? "").includes("application/json");
    const body = isJson && raw !== "" ? (JSON.parse(raw) as Fields) : raw;
    const json = (status: number, payload: unknown) =>
      route.fulfill({ status, contentType: "application/json", body: JSON.stringify(payload) });
    const id = () => `e2efib${String(++count).padStart(8, "0")}`;
    const common = { created_at: new Date().toISOString() };

    if (method === "POST" && url.pathname === "/api/v1/fib/income") {
      calls.push({ method, path: url.pathname, body });
      const data = body as Fields;
      const entryId = id();
      const entryDate = (data.entry_date as string | null | undefined) ?? today();
      await entry("income", entryId, {
        ...data,
        entry_date: entryDate,
        category_source: "user",
        verified: false,
      });
      return json(201, {
        entry_id: entryId,
        ...data,
        entry_date: entryDate,
        category_source: "user",
        verified: false,
        ...common,
      });
    }
    if (method === "POST" && url.pathname === "/api/v1/fib/bill") {
      calls.push({ method, path: url.pathname, body });
      const data = body as Fields;
      const entryId = id();
      const entryDate = (data.entry_date as string | null | undefined) ?? today();
      const categorized = data.category !== undefined && data.category !== null;
      if (!categorized) {
        uncategorized.push(entryId);
      }
      await entry("bills", entryId, {
        ...data,
        entry_date: entryDate,
        ...(categorized ? { category_source: "user" } : {}),
      });
      return json(201, {
        entry_id: entryId,
        ...data,
        entry_date: entryDate,
        category_source: categorized ? "user" : null,
        ...common,
      });
    }
    if (method === "POST" && url.pathname === "/api/v1/fib/savings") {
      calls.push({ method, path: url.pathname, body });
      const data = body as Fields;
      const entryId = id();
      const entryDate = (data.entry_date as string | null | undefined) ?? today();
      await entry("savings", entryId, { ...data, entry_date: entryDate });
      return json(201, { entry_id: entryId, ...data, entry_date: entryDate, ...common });
    }
    if (method === "POST" && url.pathname === "/api/v1/fib/bill/scan") {
      calls.push({ method, path: url.pathname, body: "(file)" });
      if (scan === "not_a_bill") {
        return json(422, { detail: "No bill found in this file." });
      }
      if (scan === "unreadable") {
        return json(422, { detail: "The amount or currency could not be read from this bill." });
      }
      const entryId = id();
      const data = {
        amount: 48.9,
        currency: "SGD",
        vendor: "SP Services",
        bill_date: today(),
        paid: true,
        category: "utilities",
        entry_date: today(),
      };
      await entry("bills", entryId, {
        ...data,
        category_source: "model",
        category_confidence: 0.95,
        source: "bill_ocr",
      });
      return json(201, {
        entry_id: entryId,
        ...data,
        category_source: "model",
        notes: null,
        image_path: null,
        confidence: 0.95,
        paid_assumed: false,
        ...common,
      });
    }
    if (method === "POST" && url.pathname === "/api/v1/fib/categorize") {
      calls.push({ method, path: url.pathname, body });
      const sorted = uncategorized.splice(0);
      for (const entryId of sorted) {
        await updateDocument(`users/${user.uid}/bills/${entryId}`, {
          category: "utilities",
          category_source: "model",
          category_confidence: 0.9,
        });
      }
      return json(200, {
        categorized: sorted.map((entry_id) => ({
          entry_id,
          entry_type: "bill",
          category: "utilities",
          confidence: 0.9,
        })),
        skipped: 0,
        remaining: 0,
      });
    }
    if (url.pathname === "/api/v1/fib/report/export") {
      calls.push({ method, path: url.pathname, body });
      if (method === "GET" && exported === null) {
        return json(404, { detail: "No report has been exported yet." });
      }
      if (method === "POST") {
        exported = { created_at: new Date().toISOString() };
      }
      return json(method === "POST" ? 201 : 200, {
        download_url: "http://127.0.0.1/e2e/financial-identity-report.pdf",
        expires_at: new Date(Date.now() + 86_400_000).toISOString(),
        created_at: exported?.created_at,
        language: "en",
        filename: "financial-identity-report.pdf",
      });
    }
    return route.fallback();
  });

  return {
    calls,
    scanWill: (outcome) => {
      scan = outcome;
    },
    to: (method, pattern) =>
      calls.filter((call) => call.method === method && pattern.test(call.path)),
  };
}
