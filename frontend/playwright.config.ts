import { defineConfig, devices } from "@playwright/test";

// End-to-end tests drive a real browser against a running copy of the app (NF-F0-014).
//
// Default: the production build served locally by `vite preview`, which needs no backend and no
// sign-in, so the same tests run on a laptop and in CI. Run `pnpm build` first.
// To point them at a running site instead (a local `pnpm dev`, or a deployed address):
//   PLAYWRIGHT_BASE_URL=http://127.0.0.1:5173 pnpm test:e2e
const externalUrl = process.env.PLAYWRIGHT_BASE_URL;
const PREVIEW_PORT = 4173;

export default defineConfig({
  testDir: "./e2e",
  // A test left as `.only` must not pass a pull request with the rest unrun.
  forbidOnly: Boolean(process.env.CI),
  // One retry in CI: a second failure with a trace is a real failure, a flake is not.
  retries: process.env.CI ? 1 : 0,
  reporter: process.env.CI
    ? [["github"], ["html", { open: "never" }]]
    : [["list"], ["html", { open: "never" }]],
  use: {
    baseURL: externalUrl ?? `http://127.0.0.1:${PREVIEW_PORT}`,
    trace: "on-first-retry",
    // The app's service worker would answer from its cache before a test's own route handlers
    // (page.route) could, so a mocked API answer could be bypassed or served stale.
    serviceWorkers: "block",
  },
  // A phone and a desktop, both on Chromium: workers use phones first, so the phone is not a
  // second thought. Firefox and WebKit are opt-in below (NF-HR-005).
  projects: [
    { name: "desktop", use: { ...devices["Desktop Chrome"] } },
    { name: "mobile", use: { ...devices["Pixel 5"] } },
    // The other engines (NF-HR-005): off by default, so CI keeps its two projects and its minutes.
    // `CROSS_BROWSER=1 pnpm exec playwright install firefox webkit` once, then
    // `CROSS_BROWSER=1 pnpm test:e2e --project=firefox --project=webkit-iphone`. WebKit with an
    // iPhone profile stands in for Safari on iOS: it is the same engine, not a real phone.
    ...(process.env.CROSS_BROWSER === "1"
      ? [
          { name: "firefox", use: { ...devices["Desktop Firefox"] } },
          { name: "webkit-iphone", use: { ...devices["iPhone 13"] } },
        ]
      : []),
  ],
  webServer: externalUrl
    ? undefined
    : {
        command: `pnpm preview --host 127.0.0.1 --port ${PREVIEW_PORT} --strictPort`,
        url: `http://127.0.0.1:${PREVIEW_PORT}`,
        reuseExistingServer: !process.env.CI,
        timeout: 60_000,
      },
});
