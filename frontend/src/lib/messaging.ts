import { getMessaging, getToken, isSupported, onMessage, type Messaging } from "firebase/messaging";

import { firebaseApp } from "@/lib/firebase";

const SENDER_ID = import.meta.env.VITE_FIREBASE_MESSAGING_SENDER_ID;
const VAPID_KEY = import.meta.env.VITE_FIREBASE_VAPID_KEY;
// Its own scope, not the default "/": the app already has vite-plugin-pwa's own service
// worker controlling "/", and two workers both claiming that scope would fight over which
// one answers fetch events. Firebase's own docs use this same coexistence pattern.
const SW_SCOPE = "/firebase-cloud-messaging-push-scope";

/** Both env vars set is the only thing needed to attempt push; both unset is the normal,
 * fully-supported state for anyone who hasn't configured Firebase Cloud Messaging. */
export const isPushConfigured = Boolean(SENDER_ID) && Boolean(VAPID_KEY);

let messagingPromise: Promise<Messaging | null> | null = null;

function messagingConfig(): Promise<Messaging | null> {
  if (!isPushConfigured || !("Notification" in window) || !("serviceWorker" in navigator)) {
    return Promise.resolve(null);
  }
  messagingPromise ??= isSupported().then((supported) =>
    supported ? getMessaging(firebaseApp) : null
  );
  return messagingPromise;
}

/** `"unsupported"` covers not configured, not a supporting browser, and no Notification API —
 * the caller shows one "not available here" state for all three, never an error. */
export function pushPermission(): NotificationPermission | "unsupported" {
  if (!isPushConfigured || !("Notification" in window)) {
    return "unsupported";
  }
  return Notification.permission;
}

async function swRegistration(): Promise<ServiceWorkerRegistration> {
  // Config values are public identifiers (frontend/.env.example), safe in a URL; a static
  // file in public/ can't read import.meta.env, so it reads them from its own query string.
  const params = new URLSearchParams({
    apiKey: import.meta.env.VITE_FIREBASE_API_KEY,
    projectId: import.meta.env.VITE_FIREBASE_PROJECT_ID,
    messagingSenderId: SENDER_ID ?? "",
    appId: import.meta.env.VITE_FIREBASE_APP_ID,
  });
  return navigator.serviceWorker.register(`/firebase-messaging-sw.js?${params.toString()}`, {
    scope: SW_SCOPE,
  });
}

/**
 * Ask for notification permission and register a push token for this browser.
 *
 * Returns null whenever push can't happen here — not configured, not supported, or the
 * person declined — never throws: the caller always has a feed that works from Firestore
 * regardless, so a missing token is a smaller feature, not a failure.
 */
export async function requestPushToken(): Promise<string | null> {
  const messaging = await messagingConfig();
  if (messaging === null) {
    return null;
  }
  const permission = await Notification.requestPermission();
  if (permission !== "granted") {
    return null;
  }
  try {
    const registration = await swRegistration();
    const token = await getToken(messaging, {
      vapidKey: VAPID_KEY,
      serviceWorkerRegistration: registration,
    });
    return token || null;
  } catch {
    return null;
  }
}

/**
 * Foreground pushes only (the tab open and focused); a backgrounded or closed tab is the
 * service worker's job (public/firebase-messaging-sw.js). No-op unsubscribe when push isn't
 * configured, so the caller can always call the returned function on unmount.
 */
export async function listenForPushes(
  onPush: (title: string, body: string) => void
): Promise<() => void> {
  const messaging = await messagingConfig();
  if (messaging === null) {
    return () => {};
  }
  return onMessage(messaging, (payload) => {
    onPush(payload.notification?.title ?? "", payload.notification?.body ?? "");
  });
}
