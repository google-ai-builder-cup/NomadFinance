import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vitest/config";
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
  test: {
    // Unit tests sit beside the code (`pnpm test` runs src). tests/rules needs the Firebase
    // emulators and has its own script (`pnpm test:rules`).
    include: ["src/**/*.test.{ts,tsx}", "tests/**/*.test.ts"],
    coverage: {
      provider: "v8",
      include: ["src/**/*.{ts,tsx}"],
      exclude: ["src/**/*.test.{ts,tsx}", "src/**/*.d.ts", "src/main.tsx"],
      reporter: ["text-summary", "json-summary"],
      // Measured on 2026-10-06: 16.6% of lines overall, src/utils 78%, src/lib 40%. Most screens
      // have no unit test yet, so the overall floors only stop coverage from collapsing; raise
      // them as tests are added (NF-F0-010). The two folders that are tested hold their level.
      thresholds: {
        lines: 15,
        statements: 15,
        functions: 13,
        branches: 15,
        "src/utils/**": { lines: 70, statements: 70 },
        "src/lib/**": { lines: 35, statements: 35 },
      },
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
