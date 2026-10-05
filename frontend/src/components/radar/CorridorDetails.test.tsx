import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import CorridorDetails from "@/components/radar/CorridorDetails";
import en from "@/i18n/en.json";
import type { RadarEntityProfile, RadarReportSummary } from "@/types/radar";

const reportsFor = vi.hoisted(() => ({
  state: "success" as "success" | "pending" | "error",
  data: [] as RadarReportSummary[],
}));

vi.mock("@/hooks/useRadar", () => ({
  useEntityReports: () => ({
    isPending: reportsFor.state === "pending",
    isError: reportsFor.state === "error",
    isSuccess: reportsFor.state === "success",
    data: reportsFor.state === "success" ? reportsFor.data : undefined,
    refetch: () => undefined,
  }),
}));
// The real hook needs the i18next instance; the strings are what is under test, so read en.json.
vi.mock("@/hooks/useI18n", () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, string | number>) => {
      const text = key
        .split(".")
        .reduce<unknown>((node, part) => (node as Record<string, unknown>)?.[part], en);
      return typeof text === "string"
        ? text.replace(/{{(\w+)}}/g, (_, name: string) => String(values?.[name] ?? ""))
        : key;
    },
  }),
}));

function entity(n: number, over: Partial<RadarEntityProfile> = {}): RadarEntityProfile {
  return {
    slug: `business-${n}`,
    name: `Business ${n}`,
    entity_type: "recruitment_agency",
    corridors: ["SG-IN"],
    host_countries: ["SG"],
    report_count: 7 - n,
    incident_count: 1,
    violation_counts: {},
    community_rating: null,
    risk_level: "high",
    flagged: true,
    ...over,
  };
}

function report(n: number, over: Partial<RadarReportSummary> = {}): RadarReportSummary {
  return {
    report_id: `r${n}`,
    violation_type: "hidden_fees",
    description: `Original text ${n}`,
    summary: `Summary ${n}`,
    language: "en",
    corridor_id: "SG-IN",
    host_country: "SG",
    source: "user",
    created_at: "2026-09-20T10:00:00Z",
    ...over,
  };
}

function render(props: Partial<Parameters<typeof CorridorDetails>[0]> = {}): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <CorridorDetails
        corridorId="SG-IN"
        level={3}
        reportCount={7}
        entities={[entity(1)]}
        {...props}
      />
    </MemoryRouter>
  );
}

describe("CorridorDetails", () => {
  beforeEach(() => {
    reportsFor.state = "success";
    reportsFor.data = [report(1)];
  });

  it("starts closed: the route and its total, and nothing fetched or listed yet", () => {
    const markup = render();

    expect(markup).toContain('aria-expanded="false"');
    expect(markup).toContain("Reports: 7");
    expect(markup).not.toContain("Business 1");
  });

  it("opens to the businesses on the route with their reports and a link to each profile", () => {
    const markup = render({ defaultOpen: true });

    expect(markup).toContain('aria-expanded="true"');
    expect(markup).toContain("Business 1");
    expect(markup).toContain("Summary 1");
    expect(markup).toContain('href="/radar/entity/business-1"');
    expect(markup).toContain("High risk");
  });

  it("says so, and offers a report, when nobody was reported on the route", () => {
    const markup = render({ defaultOpen: true, entities: [], reportCount: 0, level: 0 });

    expect(markup).toContain(en.radar.heatmap.noBusinesses);
    expect(markup).toContain('href="/radar/report"');
  });

  it("shows three reports and offers the rest", () => {
    reportsFor.data = [1, 2, 3, 4, 5].map((n) => report(n));
    const markup = render({ defaultOpen: true });

    expect(markup).toContain("Summary 3");
    expect(markup).not.toContain("Summary 4");
    expect(markup).toContain("Show all 5 reports");
  });

  it("shows five businesses and offers the rest", () => {
    const markup = render({
      defaultOpen: true,
      entities: [1, 2, 3, 4, 5, 6, 7].map((n) => entity(n)),
    });

    expect(markup).toContain("Business 5");
    expect(markup).not.toContain("Business 6");
    expect(markup).toContain("Show 2 more businesses");
  });

  it("names the route when a report is about a different one", () => {
    reportsFor.data = [report(1), report(2, { corridor_id: "AU-IN" })];
    const markup = render({ defaultOpen: true });

    expect(markup).toContain("Route: Australia → India");
    expect(markup.match(/Route: /g)).toHaveLength(1);
  });

  it("falls back to the original text when a report has no summary", () => {
    reportsFor.data = [report(1, { summary: null })];

    expect(render({ defaultOpen: true })).toContain("Original text 1");
  });

  it("shows a loading state and an error state instead of an empty list", () => {
    reportsFor.state = "pending";
    expect(render({ defaultOpen: true })).toContain('role="status"');

    reportsFor.state = "error";
    const failed = render({ defaultOpen: true });
    expect(failed).toContain(en.radar.heatmap.reportsLoadError);
    expect(failed).toContain(en.common.retry);
  });
});
