import type { Page, Route } from "@playwright/test";

// Remittance X-Ray's backend for the browser tests (NF-HR-005): the comparison, the trend, the
// savings figure, the advice and the transfer log. The prices are made up and small (three
// services), the shapes are the ones of `frontend/src/types/remittance.ts`.

export interface RemittanceCall {
  method: string;
  path: string;
  body: unknown;
}

export interface FakeRemittance {
  calls: RemittanceCall[];
  /** What the advice call does next: write advice, or fail with this status. */
  adviceWill(outcome: "ok" | 502 | 503 | 504): void;
  to(method: string, pattern: RegExp): RemittanceCall[];
}

const SURVEY = {
  period: "2025_1Q",
  surveyed_from: "2025-02-05",
  surveyed_to: "2025-02-28",
  source_name: "The World Bank, Remittance Prices Worldwide",
  source_url: "http://remittanceprices.worldbank.org",
  attribution:
    "The World Bank, Remittance Prices Worldwide, available at http://remittanceprices.worldbank.org",
};

function provider(rank: number, firm: string, rpwId: number, fee: number, receives: number) {
  return {
    rpw_id: rpwId,
    firm,
    firm_type: "Money Transfer Operator",
    payment_instrument: "Debit card",
    access_point: "Online",
    pickup_method: "Bank account",
    speed: "Within an hour",
    speed_order: rank,
    network_coverage: null,
    note: null,
    payout_currency: "INR",
    comparable: true,
    rank,
    estimated: false,
    fee,
    fx_margin_pct: rank,
    rate_cost: rank * 3,
    total_cost: fee + rank * 3,
    total_cost_pct: (fee + rank * 3) / 5,
    recipient_receives: receives,
    lost_to_costs: 100 * rank,
    less_than_best: rank === 1 ? 0 : 100 * (rank - 1),
    flagged: false,
    flag_report_count: null,
  };
}

function comparison(corridorId: string, amount: number) {
  const providers = [
    provider(1, "Wise", 101, 4.5, 30800),
    provider(2, "Western Union", 102, 6, 30500),
    provider(3, "Remitly", 103, 9, 29400),
  ];
  return {
    corridor_id: corridorId,
    send_amount: amount,
    send_currency: corridorId.split("-")[0] === "AU" ? "AUD" : "SGD",
    receive_currency: "INR",
    rate: {
      pair: "SGD_INR",
      rate: 62,
      source: "live",
      provider: "frankfurter",
      rate_date: "2026-10-12",
      fetched_at: "2026-10-12T08:00:00Z",
      stale: false,
    },
    survey: SURVEY,
    providers,
    summary: {
      comparable_count: 3,
      best_rpw_id: 101,
      best_firm: "Wise",
      best_recipient_receives: 30800,
      worst_rpw_id: 103,
      worst_firm: "Remitly",
      worst_recipient_receives: 29400,
      extra_vs_worst: 1400,
      mid_market_receives: 31000,
      median_total_cost_pct: 1.2,
    },
  };
}

/** Answers `/api/v1/remittance/**` for the page. Anything else goes on to the next handler. */
export async function remittanceApi(page: Page): Promise<FakeRemittance> {
  const calls: RemittanceCall[] = [];
  let advice: "ok" | 502 | 503 | 504 = "ok";
  const json = (route: Route, status: number, body: unknown) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

  await page.route("**/api/v1/remittance/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const raw = request.postData();
    const body = raw ? (JSON.parse(raw) as Record<string, unknown>) : null;
    calls.push({ method, path: url.pathname, body });

    if (method === "POST" && url.pathname.endsWith("/compare")) {
      return json(route, 200, comparison(String(body?.corridor_id), Number(body?.amount)));
    }
    if (method === "GET" && url.pathname.endsWith("/trends")) {
      const days = Number(url.searchParams.get("days") ?? 30);
      const points = Array.from({ length: 6 }, (_, n) => ({
        date: `2026-10-0${n + 1}`,
        rate: 61.5 + n * 0.1,
      }));
      return json(route, 200, {
        corridor_id: url.searchParams.get("corridor_id"),
        pair: "SGD_INR",
        base_currency: "SGD",
        quote_currency: "INR",
        days,
        points,
        summary: {
          first: points[0],
          latest: points[5],
          change_pct: 0.8,
          low: points[0],
          high: points[5],
          average: 61.75,
        },
        last_date: "2026-10-06",
        best_day: null,
        best_day_reason: "not_enough_history",
        weeks_analysed: 1,
        weekdays: [],
        providers: ["Wise"],
      });
    }
    if (method === "GET" && url.pathname.endsWith("/savings")) {
      return json(route, 200, {
        corridor_id: url.searchParams.get("corridor_id"),
        send_amount: Number(url.searchParams.get("amount")),
        send_currency: "SGD",
        receive_currency: "INR",
        months_requested: 6,
        months_used: 2,
        best_rpw_id: 101,
        best_firm: "Wise",
        worst_rpw_id: 103,
        worst_firm: "Remitly",
        total_best_receives: 61600,
        total_worst_receives: 58800,
        total_savings: 2800,
        months: [],
        survey: SURVEY,
      });
    }
    if (method === "POST" && url.pathname.endsWith("/recommend")) {
      if (advice !== "ok") {
        return json(route, advice, { code: "ai_failed", message: "The AI service failed." });
      }
      return json(route, 200, {
        corridor_id: "SG-IN",
        target_language: "en",
        recommended_rpw_id: 101,
        recommended_firm: "Wise",
        headline: "Wise gives your family the most.",
        explanation: "It has the lowest total cost for this amount.",
        timing_tip: null,
      });
    }
    if (method === "POST" && url.pathname.endsWith("/log")) {
      const sent = (body?.comparison ?? {}) as { corridor_id?: string; send_amount?: number };
      return json(route, 201, {
        transfer_id: `t_${calls.length}`,
        corridor_id: sent.corridor_id ?? "SG-IN",
        provider_rpw_id: body?.rpw_id,
        provider_name: "Wise",
        send_amount: sent.send_amount ?? 500,
        send_currency: "SGD",
        receive_amount: 30800,
        receive_currency: "INR",
        fee: 4.5,
        mid_market_rate: 62,
        cost_pct: 1.2,
        entry_date: "2026-10-13",
        notes: null,
      });
    }
    return route.fallback();
  });

  return {
    calls,
    adviceWill(outcome) {
      advice = outcome;
    },
    to(method, pattern) {
      return calls.filter((call) => call.method === method && pattern.test(call.path));
    },
  };
}
