import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      // "prompt": main.tsx shows a "New version available" toast and the person chooses when
      // to load it, instead of the page being swapped silently (NF-P1-026).
      registerType: "prompt",
      // We register the SW ourselves in main.tsx via virtual:pwa-register,
      // so the plugin shouldn't also inject its own registration script.
      injectRegister: false,
      includeAssets: ["favicon.ico", "favicon.svg", "apple-touch-icon.png"],
      manifest: {
        name: "NomadFinance",
        short_name: "NomadFinance",
        description: "Financial protection for migrant workers.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#ffffff",
        // Brand primary "Nomad Teal" (NF-P1-024) — see docs/runbooks/NF-P1-024-brand-assets.md
        theme_color: "#0B5D71",
        icons: [
          { src: "/icons/pwa-192x192.png", sizes: "192x192", type: "image/png", purpose: "any" },
          { src: "/icons/pwa-512x512.png", sizes: "512x512", type: "image/png", purpose: "any" },
          {
            src: "/icons/maskable-512x512.png",
            sizes: "512x512",
            type: "image/png",
            purpose: "maskable",
          },
        ],
      },
      workbox: {
        // The whole built app, so it opens offline and every deploy changes sw.js (which is
        // how the browser notices a new version).
        globPatterns: ["**/*.{js,css,html,svg,png,ico,webmanifest}"],
        // Its own service worker (NF-P3-009, registered on its own scope in
        // lib/messaging.ts), not part of the installable app shell: a service worker script
        // must never be precached by another one, or the browser's own update check for it
        // (a fresh network fetch) would be served a stale cached copy instead.
        // Also not the iOS launch images (public/splash): there are eleven sizes and a phone
        // uses one, which iOS fetches itself when the app is added to the home screen. That
        // was a quarter of what every first visit downloaded in the background (NF-P4-003).
        globIgnores: ["firebase-messaging-sw.js", "splash/**"],
        navigateFallbackDenylist: [/^\/__\//],
      },
    }),
  ],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // The backend is a different origin, so in development the browser talks to Vite and
    // Vite forwards /api to it (no CORS needed). A deployed site uses VITE_API_BASE_URL.
    proxy: {
      "/api": { target: "http://127.0.0.1:8080", changeOrigin: true },
    },
  },
});
