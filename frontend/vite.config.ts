import path from "node:path";
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    VitePWA({
      registerType: "autoUpdate",
      // We register the SW ourselves in main.tsx via virtual:pwa-register,
      // so the plugin shouldn't also inject its own registration script.
      injectRegister: false,
      includeAssets: ["favicon.ico", "favicon.svg", "apple-touch-icon.png"],
      manifest: {
        // TODO(Aditya): swap name/colors/icons for real branding from NF-P1-024
        name: "NomadFinance",
        short_name: "NomadFinance",
        description: "Financial protection for migrant workers.",
        start_url: "/",
        scope: "/",
        display: "standalone",
        background_color: "#ffffff",
        theme_color: "#0f172a",
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
        globPatterns: ["*/.{js,css,html,svg,png,ico,webmanifest}"],
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
  },
});
