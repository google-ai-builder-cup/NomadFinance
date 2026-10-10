// Must match frontend/firestore.rules and docs/data-model/collections/users.md:
// the rules reject any other value.

export const HOST_COUNTRIES = ["SG", "MY", "HK", "JP", "KR", "AU"] as const;
export type HostCountry = (typeof HOST_COUNTRIES)[number];

export function isHostCountry(value: unknown): value is HostCountry {
  return (HOST_COUNTRIES as readonly unknown[]).includes(value);
}

export const HOME_COUNTRIES = ["PH", "IN", "ID", "NP", "BD"] as const;
export type HomeCountry = (typeof HOME_COUNTRIES)[number];

export const JOB_TYPES = [
  "domestic_worker",
  "manufacturing_worker",
  "care_worker",
  "plantation_worker",
  "construction_worker",
  "working_holiday",
  "other",
] as const;
export type JobType = (typeof JOB_TYPES)[number];

export const LANGUAGE_CODES = ["en", "hi", "tl", "id", "ne", "bn"] as const;
export type LanguageCode = (typeof LANGUAGE_CODES)[number];

export function isLanguageCode(value: string | undefined): value is LanguageCode {
  return (LANGUAGE_CODES as readonly string[]).includes(value ?? "");
}

// The six money corridors of the project scope (data-scripts/src/config.py), host-home.
export const CORRIDOR_IDS = ["SG-PH", "SG-IN", "AU-IN", "MY-ID", "JP-PH", "AU-PH"] as const;
export type CorridorId = (typeof CORRIDOR_IDS)[number];
