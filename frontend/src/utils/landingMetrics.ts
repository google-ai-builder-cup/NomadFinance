// Every static number on the landing page comes from here, never from JSX. A figure is either a
// sourced industry fact (with its source shown beside it) or a property of this system. Nothing
// here is invented. The platform totals are not here: they are read live from
// `GET /api/v1/public/stats`, and one that cannot be read is left out.

export interface IndustryFact {
  /** Number the card counts up to. */
  value: number;
  prefix?: string;
  suffix: string;
  /** Publisher and publication, shown as a small caption under the figure. */
  source: string;
}

export const INDUSTRY_FACTS = {
  // UN DESA counts international migrants, a wider group than migrant workers (the ILO puts
  // workers at roughly 168 million), so the card says "international migrants".
  migrants: {
    value: 280,
    suffix: "M+",
    source: "UN DESA, International Migrant Stock 2020",
  },
  remittances: {
    value: 650,
    prefix: "$",
    suffix: "B+",
    source: "World Bank, Migration and Development Brief",
  },
  // Derived, not published: the World Bank's average cost of sending money (6.49% in Q1 2025,
  // rounded down to the 6% floor used below) applied to the USD 685B recorded for 2024, which is
  // about 41B. The card is captioned "derived". Checked against the World Bank 2024 brief and
  // RPW Q1 2025 on 2026-10-15; recheck when either is reissued.
  lostToFees: {
    value: 41,
    prefix: "$",
    suffix: "B",
    source: "World Bank Remittance Prices Worldwide, applied to flows (derived)",
  },
  // UN SDG target 10.c: transaction costs below 3% by 2030.
  target: {
    value: 3,
    prefix: "<",
    suffix: "%",
    source: "UN SDG 10.c; World Bank Remittance Prices Worldwide",
  },
} as const satisfies Record<string, IndustryFact>;

// The global average is still above this, per the World Bank's Remittance Prices Worldwide.
export const GLOBAL_AVERAGE_COST_FLOOR_PCT = 6;
export const COST_TARGET_PCT = 3;

/** How often the Cloud Scheduler job refreshes FX rates (infra/cloud-scheduler/refresh-rates.yaml). */
export const FX_REFRESH_HOURS = 2;

/** The same word in each of the six languages, for the cycling "protected" line. These are the
 * languages' own words, like their names in the language selector: not translated. */
export const PROTECTED_WORDS = [
  "Protected",
  "सुरक्षित",
  "Protektado",
  "Terlindungi",
  "संरक्षित",
  "সুরক্ষিত",
] as const;
