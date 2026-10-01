import { describe, expect, it } from "vitest";

import type { RadarEntityProfile } from "@/types/radar";
import { findFlaggedEntity } from "@/utils/flaggedProviders";

function entity(over: Partial<RadarEntityProfile> & { slug: string }): RadarEntityProfile {
  return {
    name: over.slug,
    entity_type: "money_transfer_operator",
    corridors: ["SG-IN"],
    host_countries: ["SG"],
    report_count: 3,
    incident_count: 3,
    violation_counts: {},
    community_rating: 3.5,
    risk_level: "medium",
    flagged: true,
    ...over,
  };
}

describe("findFlaggedEntity", () => {
  it("matches a flagged operator by the slug of the provider's name", () => {
    const flagged = entity({ slug: "example-remit" });

    expect(findFlaggedEntity("Example Remit", [entity({ slug: "other" }), flagged])).toBe(flagged);
  });

  it("ignores case, accents and punctuation in the provider's name", () => {
    const flagged = entity({ slug: "pnb-philippines-national-bank" });

    expect(findFlaggedEntity("PNB (Philippines National Bank)", [flagged])).toBe(flagged);
    expect(findFlaggedEntity("pnb  PHILIPPINES national bank", [flagged])).toBe(flagged);
  });

  it("matches through an alias when the plain slug differs", () => {
    const flagged = entity({ slug: "pnb", aliases: ["PNB (Philippines National Bank)"] });

    expect(findFlaggedEntity("PNB (Philippines National Bank)", [flagged])).toBe(flagged);
  });

  it("shows nothing for a profile that is not flagged (one unverified report)", () => {
    expect(
      findFlaggedEntity("Example Remit", [entity({ slug: "example-remit", flagged: false })])
    ).toBeNull();
  });

  it("never matches an employer or an agency that shares the name", () => {
    expect(
      findFlaggedEntity("Example Remit", [
        entity({ slug: "example-remit", entity_type: "employer" }),
        entity({ slug: "example-remit", entity_type: "recruitment_agency" }),
      ])
    ).toBeNull();
  });

  it("returns null for no entities, no match, or a name with nothing to slug", () => {
    expect(findFlaggedEntity("Wise", [])).toBeNull();
    expect(findFlaggedEntity("Wise", [entity({ slug: "western-union" })])).toBeNull();
    expect(findFlaggedEntity("---", [entity({ slug: "" })])).toBeNull();
  });
});
