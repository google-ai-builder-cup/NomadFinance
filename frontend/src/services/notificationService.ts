import {
  collection,
  doc,
  getDocs,
  orderBy,
  query,
  serverTimestamp,
  updateDoc,
} from "firebase/firestore";

import { db } from "@/lib/firebase";
import type { AppNotification } from "@/types/notification";

function notificationsRef(uid: string) {
  return collection(db, "users", uid, "notifications");
}

/**
 * Every notification for the signed-in worker, newest first. Small, per-user collection
 * (radar alerts and, eventually, reminders): a single `created_at` sort needs no composite
 * index, so unread-first grouping happens client-side, not in the query.
 */
export async function listNotifications(uid: string): Promise<AppNotification[]> {
  const notificationsQuery = query(notificationsRef(uid), orderBy("created_at", "desc"));
  const snapshot = await getDocs(notificationsQuery);
  return snapshot.docs.map((notification) => ({
    ...(notification.data() as Omit<AppNotification, "id">),
    id: notification.id,
  }));
}

/** Mark one notification read. The rules (NF-P1-014) accept only `read` and `read_at` here. */
export async function markNotificationRead(uid: string, id: string): Promise<void> {
  await updateDoc(doc(db, "users", uid, "notifications", id), {
    read: true,
    read_at: serverTimestamp(),
  });
}
