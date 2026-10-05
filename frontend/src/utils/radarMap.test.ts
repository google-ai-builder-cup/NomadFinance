import { describe, expect, it } from "vitest";

import type { RadarEntityProfile } from "@/types/radar";
import { corridorHeat, entitiesOnCorridor, entityMarkers, filterEntities } from "@/utils/radarMap";

function entity(over: Partial<RadarEntityProfile>): RadarEntityProfile {
  return {
    slug: "a",
    name: "A",
    entity_type: "money_transfer_operator",
    corridors: ["SG-PH"],
    host_countries: ["SG"],
    report_count: 1,
    incident_count: 1,
    violation_counts: {},
    community_rating: null,
    risk_level: "low",
    flagged: false,
    ...over,
  };
}

describe("corridorHeat", () => {
  it("lists all six corridors, with no heat when there are no reports", () => {
    const heat = corridorHeat([]);
    expect(heat).toHaveLength(6);
    expect(heat.every((corridor) => corridor.level === 0 && corridor.reportCount === 0)).toBe(true);
  });

  it("adds up reports per corridor and scales the level to the busiest one", () => {
    const heat = corridorHeat([
      entity({ slug: "a", report_count: 4 }),
      entity({ slug: "b", report_count: 2 }),
      entity({ slug: "c", corridors: ["JP-PH"], report_count: 3 }),
      entity({ slug: "d", corridors: ["AU-IN"], report_count: 1 }),
    ]);
    const byId = Object.fromEntries(heat.map((corridor) => [corridor.id, corridor]));
    expect(byId["SG-PH"]).toMatchObject({ reportCount: 6, entityCount: 2, level: 3 });
    expect(byId["JP-PH"].level).toBe(2);
    expect(byId["AU-IN"].level).toBe(1);
    expect(byId["MY-ID"].level).toBe(0);
  });

  it("ignores an employer with no corridor instead of failing", () => {
    const heat = corridorHeat([entity({ corridors: undefined as never })]);
    expect(heat.every((corridor) => corridor.reportCount === 0)).toBe(true);
  });
});

describe("filterEntities", () => {
  it("keeps only the chosen type, or everything for all", () => {
    const list = [entity({ slug: "a" }), entity({ slug: "b", entity_type: "employer" })];
    expect(filterEntities(list, "employer").map((e) => e.slug)).toEqual(["b"]);
    expect(filterEntities(list, "all")).toHaveLength(2);
  });
});

describe("entityMarkers", () => {
  it("marks only flagged businesses, each on its host country", () => {
    const markers = entityMarkers([
      entity({ slug: "a", flagged: true }),
      entity({ slug: "b", flagged: false }),
      entity({ slug: "c", flagged: true, corridors: [], host_countries: ["KR"] }),
    ]);
    expect(markers.map((marker) => marker.entity.slug)).toEqual(["a", "c"]);
    expect(markers[0].position).toEqual([1.35, 103.82]);
  });

  it("does not stack two businesses of one country on the same point", () => {
    const [first, second] = entityMarkers([
      entity({ slug: "a", flagged: true }),
      entity({ slug: "b", flagged: true }),
    ]);
    expect(second.position).not.toEqual(first.position);
  });
});

describe("entitiesOnCorridor", () => {
  const list = [
    entity({ slug: "quiet", name: "Quiet Remit", report_count: 1, corridors: ["SG-PH"] }),
    entity({ slug: "busy", name: "Busy Agency", report_count: 6, corridors: ["SG-PH", "SG-IN"] }),
    entity({ slug: "other", name: "Other Co", report_count: 9, corridors: ["AU-IN"] }),
    entity({ slug: "tie", name: "Alpha Tie", report_count: 1, corridors: ["SG-PH"] }),
  ];

  it("lists only the businesses on that route, most reports first, ties by name", () => {
    expect(entitiesOnCorridor(list, "SG-PH").map((e) => e.slug)).toEqual(["busy", "tie", "quiet"]);
  });

  it("includes a business on every route it works", () => {
    expect(entitiesOnCorridor(list, "SG-IN").map((e) => e.slug)).toEqual(["busy"]);
  });

  it("is empty for a route nobody was reported on", () => {
    expect(entitiesOnCorridor(list, "MY-ID")).toEqual([]);
  });

  it("adds up to the report total the route shows", () => {
    const total = entitiesOnCorridor(list, "SG-PH").reduce((sum, e) => sum + e.report_count, 0);

    expect(total).toBe(corridorHeat(list).find((c) => c.id === "SG-PH")?.reportCount);
  });

  it("does not reorder the list it was given", () => {
    const before = list.map((e) => e.slug);
    entitiesOnCorridor(list, "SG-PH");

    expect(list.map((e) => e.slug)).toEqual(before);
  });
});
