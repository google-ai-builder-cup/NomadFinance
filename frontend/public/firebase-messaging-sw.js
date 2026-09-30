// Background handler for push notifications (NF-P3-009): shows a system notification when a
// push arrives while this tab is not focused (or closed). A focused, open tab is handled
// in-app instead (src/lib/messaging.ts's onMessage listener); this file only runs the other
// case, and only once notification permission has actually been granted.
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

const params = new URLSearchParams(self.location.search);

firebase.initializeApp({
  apiKey: params.get("apiKey"),
  projectId: params.get("projectId"),
  messagingSenderId: params.get("messagingSenderId"),
  appId: params.get("appId"),
});

const messaging = firebase.messaging();

messaging.onBackgroundMessage((payload) => {
  const title = payload.notification?.title || "NomadFinance";
  self.registration.showNotification(title, {
    body: payload.notification?.body || "",
    icon: "/icons/pwa-192x192.png",
    data: { deep_link: payload.data?.deep_link || "/radar/alerts" },
  });
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const link = event.notification.data?.deep_link || "/radar/alerts";
  event.waitUntil(self.clients.openWindow(link));
});
