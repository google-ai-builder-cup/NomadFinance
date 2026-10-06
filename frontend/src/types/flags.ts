/** The Future Scope modules that ship dark and are switched on per user (docs/api/v2-flags.md). */
export const FEATURE_FLAGS = ["coach", "scam"] as const;

export type FeatureFlag = (typeof FEATURE_FLAGS)[number];

export type FeatureFlags = Readonly<Record<FeatureFlag, boolean>>;

/** What the app assumes until the backend says otherwise: nothing new is shown. */
export const ALL_FLAGS_OFF: FeatureFlags = { coach: false, scam: false };
