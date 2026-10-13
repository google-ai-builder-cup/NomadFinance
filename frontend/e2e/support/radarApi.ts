import type { Page, Route } from "@playwright/test";

import { type FirestoreValue, setDocument } from "./firestoreRest";

// Exploitation Radar's backend for the browser tests (NF-HR-006): the report, its evidence and the
// list of reports behind a business. The profiles and the alert feed are read by the page straight
// from Firestore, so those are written there, as the backend would (`seedEntity`).

export interface RadarCall {
  method: string;
  path: string;
  body: unknown;
}

export interface FakeRadar {
  calls: RadarCall[];
  /** What the report call does next: store it, or refuse it with this status and message. */
  reportWill(outcome: "ok" | { status: number; detail: string }): void;
  /** How long the report call takes, so a second tap can land while the first is in flight. */
  reportTakes(milliseconds: number): void;
  to(method: string, pattern: RegExp): RadarCall[];
}

export interface SeedEntity {
  slug: string;
  name: string;
  type?: "money_transfer_operator" | "recruitment_agency" | "employer";
  corridors?: string[];
  reports: number;
  incidents: number;
  flagged: boolean;
  risk?: "low" | "medium" | "high";
}

/** Writes one business profile (`radar_entities/{slug}`) the way the aggregation step does. */
export async function seedEntity(entity: SeedEntity): Promise<void> {
  const now = new Date();
  const data: { [key: string]: FirestoreValue } = {
    slug: entity.slug,
    name: entity.name,
    entity_type: entity.type ?? "money_transfer_operator",
    aliases: [],
    corridors: entity.corridors ?? ["SG-IN"],
    host_countries: ["SG"],
    report_count: entity.reports,
    incident_count: entity.incidents,
    violation_counts: { hidden_fees: entity.reports },
    first_reported_at: new Date(now.getTime() - 5 * 86_400_000),
    last_reported_at: now,
    community_rating: entity.incidents >= 2 ? 2.5 : null,
    risk_level: entity.risk ?? (entity.flagged ? "medium" : "low"),
    flagged: entity.flagged,
    updated_at: now,
    schema_version: 1,
  };
  await setDocument(`radar_entities/${entity.slug}`, data);
}

/** Answers `/api/v1/radar/**` for the page. Anything else goes on to the next handler. */
export async function radarApi(page: Page): Promise<FakeRadar> {
  const calls: RadarCall[] = [];
  let outcome: "ok" | { status: number; detail: string } = "ok";
  let delay = 0;
  const json = (route: Route, status: number, body: unknown) =>
    route.fulfill({ status, contentType: "application/json", body: JSON.stringify(body) });

  await page.route("**/api/v1/radar/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const raw = request.postData();
    const body = raw && request.headers()["content-type"]?.includes("json") ? JSON.parse(raw) : raw;
    calls.push({ method, path: url.pathname, body });

    if (method === "POST" && url.pathname.endsWith("/report")) {
      if (delay > 0) {
        await new Promise((resolve) => setTimeout(resolve, delay));
      }
      if (outcome !== "ok") {
        return json(route, outcome.status, { detail: outcome.detail });
      }
      const sent = body as Record<string, unknown>;
      return json(route, 201, {
        report_id: `rpt${String(calls.length).padStart(17, "0")}`,
        entity_type: sent.entity_type ?? "money_transfer_operator",
        entity_name: sent.entity_name ?? "Unknown",
        violation_type: "hidden_fees",
        corridor_id: sent.corridor_id ?? null,
        host_country: null,
        description: sent.description,
        summary: "A worker reports a fee that was not shown before paying.",
        created_at: new Date().toISOString(),
      });
    }
    if (method === "POST" && url.pathname.includes("/evidence")) {
      return json(route, 201, { report_id: "rpt", evidence_paths: ["radar/rpt/1.png"] });
    }
    if (method === "GET" && url.pathname.endsWith("/reports")) {
      return json(route, 200, [
        {
          report_id: "r1",
          violation_type: "hidden_fees",
          description: "The app showed a fee of 3 SGD but the receipt said 9 SGD.",
          summary: null,
          language: "en",
          corridor_id: "SG-IN",
          host_country: "SG",
          source: "user",
          scam: null,
          created_at: new Date().toISOString(),
        },
      ]);
    }
    return json(route, 404, { detail: "not stubbed" });
  });

  return {
    calls,
    reportWill: (next) => {
      outcome = next;
    },
    reportTakes: (milliseconds) => {
      delay = milliseconds;
    },
    to: (method, pattern) => calls.filter((c) => c.method === method && pattern.test(c.path)),
  };
}
