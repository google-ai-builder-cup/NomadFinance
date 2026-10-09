import type { Timestamp } from "firebase/firestore";

// `coach_checkin` is the day 30, 60 or 90 reminder of a Coach plan (NF-FC-016). A type this list
// does not know is still shown by the feed, so a newer backend never hides a notification.
export type NotificationType = "radar_alert" | "reminder" | "system" | "coach_checkin";

export interface NotificationSource {
  kind: string;
  path: string;
  /** A Coach check-in: `d30`, `d60` or `d90`. */
  milestone?: string;
}

/** `users/{uid}/notifications/{id}` (docs/data-model/collections/users.md). */
export interface AppNotification {
  id: string;
  type: NotificationType;
  title: string;
  body: string;
  language: string;
  deep_link?: string;
  source?: NotificationSource;
  read: boolean;
  read_at?: Timestamp;
  created_at: Timestamp;
  schema_version: number;
}
