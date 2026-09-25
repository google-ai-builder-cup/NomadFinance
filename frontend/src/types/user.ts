import type { Timestamp } from "firebase/firestore";

import type { HomeCountry, HostCountry, JobType, LanguageCode } from "@/types/enums";

/** Which alerts the user wants; the rules accept only these three keys. */
export interface NotificationPrefs {
  radar_alerts?: boolean;
  /** Corridor ids such as "SG-IN", at most 6 (see CORRIDOR_IDS). */
  radar_corridors?: string[];
  reminders?: boolean;
}

/** The profile fields a person may edit; the Firestore rules allow exactly these. */
export interface ProfileChanges {
  preferred_language?: LanguageCode;
  host_country?: HostCountry;
  home_country?: HomeCountry;
  job_type?: JobType;
  notification_prefs?: NotificationPrefs;
}

/** `users/{uid}` in Firestore; field names as in docs/data-model/collections/users.md. */
export interface UserProfile {
  home_country?: HomeCountry;
  host_country?: HostCountry;
  job_type?: JobType;
  preferred_language?: LanguageCode;
  /** Absent until onboarding finishes; the app shows onboarding while it is absent. */
  onboarding_completed_at?: Timestamp;
  notification_prefs?: NotificationPrefs;
  fcm_tokens?: string[];
  created_at: Timestamp;
  updated_at: Timestamp;
  schema_version: number;
}

export interface OnboardingAnswers {
  preferred_language: LanguageCode;
  host_country: HostCountry;
  home_country: HomeCountry;
  job_type: JobType;
}
