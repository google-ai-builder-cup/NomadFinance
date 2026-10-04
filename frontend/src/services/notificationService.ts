import {
  collection,
  doc,
  getCountFromServer,
  getDocs,
  limit,
  orderBy,
  query,
  serverTimestamp,
  updateDoc,
  where,
} from "firebase/firestore";

import { db } from "@/lib/firestore";
import type { AppNotification } from "@/types/notification";

function notificationsRef(uid: string) {
  return collection(db, "users", uid, "notifications");
}

/** Newest notifications a screen lists at most: enough for the alerts page, and a worker's feed
 * grows with every alert for as long as they use the app (NF-P4-003). */
export const NOTIFICATIONS_PAGE_SIZE = 50;

/**
 * The worker's newest notifications, newest first. A single `created_at` sort needs no
 * composite index, so unread-first grouping happens client-side, not in the query. The
 * limit matters: this used to read the whole collection, so the dashboard paid one read per
 * alert ever received to show two of them.
 */
export async function listNotifications(
  uid: string,
  max: number = NOTIFICATIONS_PAGE_SIZE
): Promise<AppNotification[]> {
  const notificationsQuery = query(
    notificationsRef(uid),
    orderBy("created_at", "desc"),
    limit(max)
  );
  const snapshot = await getDocs(notificationsQuery);
  return snapshot.docs.map((notification) => ({
    ...(notification.data() as Omit<AppNotification, "id">),
    id: notification.id,
  }));
}

/**
 * How many notifications are unread. An aggregation, billed as about one read per 1,000
 * matching documents rather than one per document, so the dashboard's "N new alerts" no longer
 * needs the whole feed.
 */
export async function countUnreadNotifications(uid: string): Promise<number> {
  const snapshot = await getCountFromServer(
    query(notificationsRef(uid), where("read", "==", false))
  );
  return snapshot.data().count;
}

/** Mark one notification read. The rules (NF-P1-014) accept only `read` and `read_at` here. */
export async function markNotificationRead(uid: string, id: string): Promise<void> {
  await updateDoc(doc(db, "users", uid, "notifications", id), {
    read: true,
    read_at: serverTimestamp(),
  });
}
