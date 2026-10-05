// Every number on the landing page comes from here, never from JSX. A figure is either a sourced
// industry fact (with its source shown beside it) or a measured property of this system. Nothing
// here is invented: a figure we have not measured yet is `null`, and the page shows a "pending"
// card until it is filled in.

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
  // Derived, not published: the World Bank's average cost of sending money, applied to the flow
  // above. The card is captioned "derived". Confirm the figure before the demo.
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

/** Properties of the running system that we have not benchmarked yet. */
export const MEASURED_METRICS: { contractAnalysisSeconds: number | null } = {
  // TODO(team): replace with the measured average once contract analysis has been benchmarked.
  contractAnalysisSeconds: null,
};
