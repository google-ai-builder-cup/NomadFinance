// @vitest-environment jsdom
// Accessibility and translation of the scam module's building blocks (NF-SA-019): every state of
// the result, the report sheet and the Radar block, in all six languages, checked with axe and
// for any string that would show as a raw key. The pages that fetch them are in
// src/pages/scam/scamPages.a11y.test.tsx.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import EntityReportList from "@/components/radar/EntityReportList";
import ReportSheet from "@/components/scam/ReportSheet";
import ScamResult from "@/components/scam/ScamResult";
import { setLanguage, loadNamespace } from "@/lib/i18n";
import { axeViolations, rawKeysShown } from "@/mocks/axe";
import { installFakeSpeech, voice } from "@/mocks/fakeSpeech";
import { scamResult, type ScamCase } from "@/mocks/scamResult";
import type { RadarReportSummary } from "@/types/radar";
import { LANGUAGE_CODES } from "@/types/enums";

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "alice" }, loading: false }) }));
vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

beforeAll(async () => {
  await loadNamespace("scam");
});

afterEach(async () => {
  cleanup();
  vi.unstubAllGlobals();
  await act(() => setLanguage("en"));
});

function renderScreen(ui: ReactElement) {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>
        <main>{ui}</main>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

async function inLanguage(code: string) {
  await act(() => setLanguage(code));
}

/** A screen is fit when axe finds nothing serious and no string shows as a key. */
async function expectFit(container: HTMLElement) {
  expect(await axeViolations(container)).toEqual([]);
  expect(rawKeysShown(container)).toEqual([]);
}

const RESULTS: readonly ScamCase[] = ["high", "medium", "low", "benign", "noExplainer"];

describe.each(LANGUAGE_CODES)("the result in %s", (language) => {
  it.each(RESULTS)("%s", async (name) => {
    await inLanguage(language);
    const { container } = renderScreen(
      <ScamResult result={scamResult(name)} onCheckAnother={() => undefined} />
    );

    await expectFit(container);
  });
});

describe("the result with something open or speaking", () => {
  it("with a tactic opened", async () => {
    const { container } = renderScreen(
      <ScamResult result={scamResult("high")} onCheckAnother={() => undefined} />
    );
    await userEvent.click(screen.getAllByRole("button", { name: /Pressure to hurry/ })[0]);

    await expectFit(container);
  });

  it("with the read-aloud button shown, and while it speaks", async () => {
    installFakeSpeech([voice("hi-IN")]);
    const { container } = renderScreen(
      <ScamResult result={scamResult("high")} onCheckAnother={() => undefined} />
    );
    await expectFit(container);

    await userEvent.click(screen.getByRole("button", { name: "Listen to this" }));

    await expectFit(container);
  });
});

describe.each(LANGUAGE_CODES)("the report sheet in %s", (language) => {
  it("open", async () => {
    await inLanguage(language);
    const { container } = renderScreen(
      <ReportSheet
        result={scamResult("high")}
        pending={false}
        error={null}
        onSend={() => undefined}
        onClose={() => undefined}
      />
    );

    await expectFit(container);
  });
});

const RADAR_REPORT: RadarReportSummary = {
  report_id: "r_09",
  violation_type: "scam_message",
  description: "Approved loan of 5,000 PHP. Pay in 3 days or we send your photos to your contacts.",
  summary: null,
  language: "tl",
  corridor_id: "SG-PH",
  host_country: "SG",
  source: "scam_check",
  created_at: "2026-11-05T09:20:00Z",
  scam: {
    scam_type: "loan_app_trap",
    tactics: ["fear", "urgency"],
    risk_level: "medium",
    confidence: 0.78,
    trigger_phrases: ["send your photos to all your contacts"],
    details: { amount_requested: { amount: 5000, currency: "PHP" } },
    indicators: [{ kind: "url", value: "quickloan-ph.example", flags: ["shortener"] }],
    message_language: "tl",
    input_type: "text",
  },
};

describe.each(LANGUAGE_CODES)("the scam report on the Radar entity page in %s", (language) => {
  it("with its details", async () => {
    await inLanguage(language);
    const { container } = renderScreen(<EntityReportList reports={[RADAR_REPORT]} />);

    // The details arrive with the scam strings, which the list fetches when it first needs them.
    expect(await screen.findByText("send your photos to all your contacts")).toBeTruthy();

    await expectFit(container);
  });
});
