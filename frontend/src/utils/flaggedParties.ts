import type { ContractParties } from "@/types/contract";
import type { RadarEntityProfile } from "@/types/radar";
import { slugify } from "@/utils/slug";

export type PartyRole = "employer" | "agency";

export interface FlaggedParty {
  role: PartyRole;
  /** The name as the contract writes it. */
  name: string;
  entity: RadarEntityProfile;
}

// What each role is filed under in Radar: the backend's contract signal files an employer as
// `employer` and an agency as `recruitment_agency` (services/cross_pillar/contract_to_radar.py).
const ENTITY_TYPE: Record<PartyRole, RadarEntityProfile["entity_type"]> = {
  employer: "employer",
  agency: "recruitment_agency",
};

// Legal-form words a contract prints after a business name but a worker's report usually
// leaves out ("Han River Metals Co., Ltd." against a profile for "Han River Metals Co").
const LEGAL_SUFFIXES = new Set([
  "co",
  "company",
  "corp",
  "corporation",
  "inc",
  "incorporated",
  "llc",
  "llp",
  "ltd",
  "limited",
  "plc",
  "pte",
  "pty",
  "sdn",
  "bhd",
  "berhad",
  "gmbh",
  "kk",
  "tbk",
]);

/**
 * The slug of a business name without its trailing legal-form words. Only trailing words are
 * dropped, so a name that merely contains one ("Co-op Staffing") keeps it. Looser than the
 * backend's exact slug on purpose: a contract and a worker's report rarely spell a company
 * the same way, and a missed warning costs more than a link to a profile of the same business.
 */
export function matchKey(name: string): string {
  const words = slugify(name).split("-").filter(Boolean);
  while (words.length > 1 && LEGAL_SUFFIXES.has(words[words.length - 1] ?? "")) {
    words.pop();
  }
  return words.join("-");
}

function matches(entity: RadarEntityProfile, key: string): boolean {
  return [entity.slug, entity.name, ...(entity.aliases ?? [])].some(
    (candidate) => matchKey(candidate) === key
  );
}

/**
 * The flagged radar profiles of the businesses a contract names (NF-P3-023). An employer must
 * match an `employer` profile and an agency a `recruitment_agency` one, and the profile must
 * be `flagged` (two or more distinct incidents): a different kind of business with the same
 * name, or a single unverified report, shows nothing. Of several matches the one with most
 * reports wins.
 */
export function findFlaggedParties(
  parties: ContractParties,
  entities: readonly RadarEntityProfile[]
): FlaggedParty[] {
  const named: [PartyRole, string | null][] = [
    ["employer", parties.employer_name],
    ["agency", parties.agency_name],
  ];
  const found: FlaggedParty[] = [];
  for (const [role, name] of named) {
    const key = name === null ? "" : matchKey(name);
    if (name === null || key === "") {
      continue;
    }
    const entity = entities
      .filter(
        (candidate) =>
          candidate.flagged &&
          candidate.entity_type === ENTITY_TYPE[role] &&
          matches(candidate, key)
      )
      .sort((a, b) => b.report_count - a.report_count)[0];
    if (entity !== undefined) {
      found.push({ role, name, entity });
    }
  }
  return found;
}
