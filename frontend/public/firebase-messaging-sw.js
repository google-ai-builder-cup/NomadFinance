// Background handler for push notifications (NF-P3-009, NF-FC-022): what happens to a push that
// arrives while this tab is not focused (or closed), and to a tap on it. A focused, open tab is
// handled in-app instead (src/lib/messaging.ts's onMessage listener); this file only runs the
// other case, and only once notification permission has actually been granted.
//
// Registered on its own scope ("/firebase-cloud-messaging-push-scope", see lib/messaging.ts),
// not "/": this app also has vite-plugin-pwa's own service worker controlling "/", and two
// workers both claiming the same scope would fight over which one answers fetch events.
//
// Config values come from this file's own query string, not a bundler: a static file in
// public/ is served as-is and cannot read import.meta.env. They are public identifiers
// (frontend/.env.example), safe to pass this way.

importScripts("https://www.gstatic.com/firebasejs/12.19.0/firebase-app-compat.js");
importScripts("https://www.gstatic.com/firebasejs/12.19.0/firebase-messaging-compat.js");

// The same name as PUSH_CLICK_MESSAGE in src/lib/messaging.ts, which is what listens for it.
const PUSH_CLICK_MESSAGE = "nf-push-click";
// Where a notification with no link of its own opens: the alert feed, where every push of this
// app pointed before the Coach had reminders.
const FALLBACK_LINK = "/radar/alerts";

// A link in a push is plain data, so only a path inside this app is followed. Keep in step with
// safeAppPath in src/utils/appLinks.ts (this file cannot import it).
function safeLink(link) {
  if (typeof link !== "string" || link.length === 0 || link.length > 300) {
    return FALLBACK_LINK;
  }
  if (!link.startsWith("/") || link.startsWith("//") || link.startsWith("/\\")) {
    return FALLBACK_LINK;
  }
  return /[\u0000-\u001f\u007f]/.test(link) ? FALLBACK_LINK : link;
}

// Our own notification keeps the link as `data.deep_link`; one the Firebase library showed keeps
// the whole push under `FCM_MSG`.
function linkOf(notification) {
  const data = notification.data || {};
  const pushed = data.FCM_MSG && data.FCM_MSG.data;
  return data.deep_link || (pushed && pushed.deep_link) || null;
}

async function openLink(link) {
  const windows = await self.clients.matchAll({ type: "window", includeUncontrolled: true });
  const open = windows.find((client) => new URL(client.url).origin === self.location.origin);
  if (open) {
    try {
      await open.focus();
      // This worker does not control the window, so it cannot navigate it: the app follows the link.
      open.postMessage({ type: PUSH_CLICK_MESSAGE, deep_link: link });
      return;
    } catch (error) {
      // A window that cannot be focused is replaced by a new one below.
    }
  }
  await self.clients.openWindow(link);
}

// Registered before the Firebase library creates its own click handler (below). For a push that
// carries a `notification` the library shows it itself, and its handler closes it and, with no
// link set, opens nothing; it also stops any handler after it. So ours must run first.
self.addEventListener("notificationclick", (event) => {
  const data = event.notification.data || {};
  if (!data.deep_link && !data.FCM_MSG) {
    return; // Not a notification of this app's pushes.
  }
  event.stopImmediatePropagation();
  event.notification.close();
  event.waitUntil(openLink(safeLink(linkOf(event.notification))));
});

const params = new URLSearchParams(self.location.search);

firebase.initializeApp({
  apiKey: params.get("apiKey"),
  projectId: params.get("projectId"),
  messagingSenderId: params.get("messagingSenderId"),
  appId: params.get("appId"),
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  // A push with a `notification` has already been shown by the library by the time this runs.
  // Showing it here too made two, and the library's could not be tapped. Only a push without
  // one (data only) is shown here.
  if (payload.notification) {
    return;
  }
  self.registration.showNotification("NomadFinance", {
    body: payload.data?.body || "",
    icon: "/icons/pwa-192x192.png",
    data: { deep_link: payload.data?.deep_link || FALLBACK_LINK },
  });
});
