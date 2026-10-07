import { readFileSync } from "node:fs";
import path from "node:path";

import type { Page, Route } from "@playwright/test";

// The backend's answers for the browser tests, read from docs/mocks/ (the same files the unit
// tests and the backend's drift test use), so a contract change reaches these tests too. The
// build is made with VITE_API_BASE_URL set to the preview's own address, so every call to the
// API is a request to the same origin that this module answers.
// `pnpm test:e2e` runs from frontend/, and `__dirname` does not exist in an ES module.
const MOCKS_DIR = path.resolve(process.cwd(), "../docs/mocks");

interface MockFile {
  status: number;
  headers?: Record<string, string>;
  body?: unknown;
}

export function readMock(name: string): MockFile {
  return JSON.parse(readFileSync(path.join(MOCKS_DIR, name), "utf8")) as MockFile;
}

/** The `body` of a mock, for a test that expects its text on the screen. */
export function mockBody<T>(name: string): T {
  return readMock(name).body as T;
}

export interface ApiCall {
  method: string;
  path: string;
  query: URLSearchParams;
  contentType: string;
  /** JSON as sent, or the raw form for a screenshot. */
  body: unknown;
  raw: string;
}

export interface MockApi {
  calls: ApiCall[];
  /** Calls to one route, in order. */
  to(method: string, pathPattern: RegExp): ApiCall[];
  /** The mock file the next analyze call answers with (default: a high-risk scam). */
  answerAnalyzeWith(name: string): void;
  /** The mock file the history list answers with. */
  answerHistoryWith(first: string, next?: string): void;
}

function respond(route: Route, mock: MockFile): Promise<void> {
  return route.fulfill({
    status: mock.status,
    headers: { "Content-Type": "application/json", ...mock.headers },
    body: mock.body === undefined ? "" : JSON.stringify(mock.body),
  });
}

const CHECK_MOCKS: Record<string, string> = {
  k_01: "scam/check-01-high-risk.json",
  k_02: "scam/check-02-medium-risk.json",
  k_03: "scam/check-03-low-risk.json",
  k_04: "scam/check-04-benign.json",
};

/**
 * Answers `/api/**` for the page. The scam module is switched on for this worker, and the scam
 * routes answer from the mock files; anything else is a 404 in the v2 error shape, so a screen
 * that reaches for an unmocked route fails loudly instead of waiting.
 */
export async function mockApi(page: Page): Promise<MockApi> {
  const calls: ApiCall[] = [];
  let analyze = "scam/analyze-01-high-risk.json";
  let historyFirst = "scam/checks-list-01-first-page.json";
  let historyNext = "scam/checks-list-02-last-page.json";

  await page.route("**/api/**", async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const raw = request.postData() ?? "";
    const contentType = request.headers()["content-type"] ?? "";
    let body: unknown = raw;
    if (contentType.includes("application/json") && raw !== "") {
      body = JSON.parse(raw);
    }
    calls.push({ method, path: url.pathname, query: url.searchParams, contentType, body, raw });

    if (method === "GET" && url.pathname === "/api/v2/flags") {
      return respond(route, readMock("flags/flags-scam-on.json"));
    }
    if (method === "POST" && url.pathname === "/api/v2/scam/analyze") {
      return respond(route, readMock(analyze));
    }
    if (method === "GET" && url.pathname === "/api/v2/scam/checks") {
      return respond(route, readMock(url.searchParams.has("cursor") ? historyNext : historyFirst));
    }
    const detail = /^\/api\/v2\/scam\/checks\/([^/]+)$/.exec(url.pathname);
    if (method === "GET" && detail) {
      const mock = CHECK_MOCKS[detail[1]];
      return respond(route, readMock(mock ?? "scam/check-error-not-found.json"));
    }
    if (method === "POST" && /^\/api\/v2\/scam\/checks\/[^/]+\/report$/.test(url.pathname)) {
      return respond(route, readMock("scam/report-01-created.json"));
    }
    return route.fulfill({
      status: 404,
      contentType: "application/json",
      body: JSON.stringify({ code: "not_found", message: "Not mocked", request_id: "e2e" }),
    });
  });

  return {
    calls,
    to: (method, pathPattern) =>
      calls.filter((call) => call.method === method && pathPattern.test(call.path)),
    answerAnalyzeWith: (name) => {
      analyze = name;
    },
    answerHistoryWith: (first, next) => {
      historyFirst = first;
      historyNext = next ?? historyNext;
    },
  };
}
