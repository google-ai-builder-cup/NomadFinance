import type { Timestamp } from "firebase/firestore";

export type NotificationType = "radar_alert" | "reminder" | "system";

export interface NotificationSource {
  kind: string;
  path: string;
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
