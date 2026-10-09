import { getMessaging, getToken, isSupported, onMessage, type Messaging } from "firebase/messaging";

import { firebaseApp } from "@/lib/firebase";
import { safeAppPath } from "@/utils/appLinks";

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
 *
 * `deepLink` is the in-app path the sender attached (`data.deep_link`), not yet checked: run it
 * through `safeAppPath` before following it.
 */
export async function listenForPushes(
  onPush: (title: string, body: string, deepLink?: string) => void
): Promise<() => void> {
  const messaging = await messagingConfig();
  if (messaging === null) {
    return () => {};
  }
  return onMessage(messaging, (payload) => {
    onPush(
      payload.notification?.title ?? "",
      payload.notification?.body ?? "",
      payload.data?.deep_link
    );
  });
}

/** What the service worker posts to an open window when a system notification is tapped. */
export const PUSH_CLICK_MESSAGE = "nf-push-click";

/**
 * A tap on a system notification while the app is already open. The worker cannot steer a window
 * it does not control (this app's own worker controls it, not the push one), so it focuses the
 * window and posts the link, and the app follows it with its router. The link is checked here
 * again: it came through a message, and only a path inside the app is followed.
 */
export function listenForPushClicks(onOpen: (deepLink: string) => void): () => void {
  if (!("serviceWorker" in navigator)) {
    return () => {};
  }
  const container = navigator.serviceWorker;
  const handler = (event: MessageEvent<unknown>) => {
    const data = event.data as { type?: unknown; deep_link?: unknown } | null;
    if (data?.type !== PUSH_CLICK_MESSAGE) {
      return;
    }
    const link = safeAppPath(data.deep_link);
    if (link !== null) {
      onOpen(link);
    }
  };
  container.addEventListener("message", handler);
  // A page that only adds a listener may not be sent messages until the document has finished
  // loading; this makes sure it is.
  container.startMessages?.();
  return () => container.removeEventListener("message", handler);
}
