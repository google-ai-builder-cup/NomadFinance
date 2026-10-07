// The Scam Analyzer contract through the mock API (NF-SA-002): every route of
// docs/api/v2-scam.md answers from docs/mocks/scam/, so the screens (NF-SA-015 to -018) can be
// built and tested before the backend exists. The backend checks the same files against its
// own models (backend/tests/unit/test_scam_mocks.py), so the two cannot drift apart.
import { describe, expect, it } from "vitest";

import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";

setupMockServer();

const API = "http://localhost/api/v2/scam";

async function call(path: string, init?: RequestInit) {
  const response = await fetch(`${API}${path}`, init);
  return { status: response.status, headers: response.headers, body: await response.json() };
}

const analyze = () =>
  call("/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ text: "Pay the fee today", language: "hi" }),
  });

describe("POST /api/v2/scam/analyze", () => {
  it("answers with the high-risk example by default, in Hindi, with a reported phone number", async () => {
    const { status, body } = await analyze();

    expect(status).toBe(200);
    expect(body.verdict).toMatchObject({ is_scam: true, risk_level: "high" });
    expect(body.language).toBe("hi");
    expect(body.cached).toBe(false);
    expect(body.indicators[0].seen).toMatchObject({ reports: 5, flagged: true });
  });

  it.each([
    ["analyze-02-medium-risk.json", "medium"],
    ["analyze-03-low-risk.json", "low"],
  ])("can answer with %s", async (name, risk) => {
    server.use(handlerForMock(`scam/${name}`));

    const { body } = await analyze();

    expect(body.verdict.is_scam).toBe(true);
    expect(body.verdict.risk_level).toBe(risk);
  });

  it("can answer that a message is not a scam, with a reassurance instead of next steps", async () => {
    server.use(handlerForMock("scam/analyze-04-benign.json"));

    const { body } = await analyze();

    expect(body.verdict).toMatchObject({ is_scam: false, scam_type: null });
    expect(body.explainer).toMatchObject({ kind: "benign" });
  });

  it("can answer from the cache, and with the explainer missing", async () => {
    server.use(handlerForMock("scam/analyze-05-cached.json"));
    expect((await analyze()).body.cached).toBe(true);

    server.use(handlerForMock("scam/analyze-06-explainer-unavailable.json"));
    const { status, body } = await analyze();

    expect(status).toBe(200);
    expect(body).toMatchObject({ explainer: null, explainer_status: "unavailable" });
  });

  it.each([
    ["analyze-error-text-too-long.json", 422, "validation_failed"],
    ["analyze-error-unsupported-media-type.json", 415, "unsupported_media_type"],
    ["analyze-error-image-unreadable.json", 422, "image_unreadable"],
    ["analyze-error-rate-limited.json", 429, "rate_limited"],
  ])("can refuse with %s", async (name, status, code) => {
    server.use(handlerForMock(`scam/${name}`));

    const result = await analyze();

    expect(result.status).toBe(status);
    expect(result.body.code).toBe(code);
    expect(result.body.request_id).toBe(result.headers.get("X-Request-ID"));
  });

  it("tells a rate-limited worker how long to wait", async () => {
    server.use(handlerForMock("scam/analyze-error-rate-limited.json"));

    const { headers } = await analyze();

    expect(headers.get("Retry-After")).toBe("1380");
    expect(headers.get("X-RateLimit-Limit")).toBe("20");
  });
});

describe("the history", () => {
  it("lists the checks newest first with a cursor, then the last page, then nothing", async () => {
    const first = await call("/checks?limit=3");
    expect(first.body.items.map((item: { id: string }) => item.id)).toEqual([
      "k_04",
      "k_03",
      "k_02",
    ]);
    expect(first.body.next_cursor).toEqual(expect.any(String));

    server.use(handlerForMock("scam/checks-list-02-last-page.json"));
    expect((await call("/checks?cursor=x")).body.next_cursor).toBeNull();

    server.use(handlerForMock("scam/checks-list-03-empty.json"));
    expect((await call("/checks")).body.items).toEqual([]);
  });

  it("opens each stored check, and answers 404 for one that is not there", async () => {
    expect((await call("/checks/k_01")).body.verdict.risk_level).toBe("high");
    expect((await call("/checks/k_04")).body.verdict.is_scam).toBe(false);

    const missing = await call("/checks/k_missing");

    expect(missing.status).toBe(404);
    expect(missing.body.code).toBe("not_found");
  });
});

describe("POST /api/v2/scam/checks/{id}/report", () => {
  const report = () =>
    call("/checks/k_01/report", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ indicator_ids: ["8c83cb97"] }),
    });

  it("creates the Radar report (201) that links to the scam type's profile", async () => {
    const { status, body } = await report();

    expect(status).toBe(201);
    expect(body).toMatchObject({
      already_reported: false,
      entity_slug: "scam-illegal-recruitment-fee",
    });
  });

  it("returns the same report on a second tap (200)", async () => {
    server.use(handlerForMock("scam/report-02-already-reported.json"));

    const { status, body } = await report();

    expect(status).toBe(200);
    expect(body).toMatchObject({ already_reported: true, report_id: "r_02" });
  });

  it("refuses an unknown indicator (422) and a message that was not a scam (409)", async () => {
    server.use(handlerForMock("scam/report-error-validation.json"));
    const invalid = await report();
    expect(invalid.status).toBe(422);
    expect(invalid.body.details[0].field).toBe("body.indicator_ids");

    const notScam = await call("/checks/k_04/report", { method: "POST" });
    expect(notScam.status).toBe(409);
    expect(notScam.body.code).toBe("not_a_scam");
  });
});
