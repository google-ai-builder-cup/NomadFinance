// @vitest-environment jsdom
// How a scam report reads on the Radar entity page (NF-SA-018, D-124).
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import EntityReportList from "@/components/radar/EntityReportList";
import ScamReportDetails from "@/components/radar/ScamReportDetails";
import { loadNamespace } from "@/lib/i18n";
import type { RadarReportSummary, RadarScamReport } from "@/types/radar";

beforeAll(async () => {
  await loadNamespace("scam");
});

afterEach(cleanup);

const SCAM: RadarScamReport = {
  scam_type: "loan_app_trap",
  tactics: ["fear", "urgency"],
  risk_level: "medium",
  confidence: 0.78,
  trigger_phrases: ["send your photos to all your contacts"],
  details: { amount_requested: { amount: 5000, currency: "PHP" } },
  indicators: [{ kind: "url", value: "quickloan-ph.example", flags: ["shortener"] }],
  message_language: "tl",
  input_type: "text",
};

const REPORT: RadarReportSummary = {
  report_id: "r_09",
  violation_type: "scam_message",
  description: "Approved loan of 5,000 PHP. Pay in 3 days or we send your photos to your contacts.",
  summary: null,
  language: "tl",
  corridor_id: "SG-PH",
  host_country: "SG",
  source: "scam_check",
  scam: SCAM,
  created_at: "2026-11-05T09:20:00Z",
};

describe("ScamReportDetails", () => {
  it("shows the risk, the tricks, the giveaway words, what it asked for and the contacts", () => {
    render(<ScamReportDetails scam={SCAM} />);

    expect(screen.getByText("Medium risk")).toBeTruthy();
    expect(screen.getByText("Scaring you")).toBeTruthy();
    expect(screen.getByText("Pressure to hurry")).toBeTruthy();
    expect(screen.getByText("send your photos to all your contacts")).toBeTruthy();
    expect(screen.getByText(/5,000/)).toBeTruthy();
    expect(screen.getByText("quickloan-ph.example")).toBeTruthy();
    expect(screen.getByText(/Shortened link/)).toBeTruthy();
  });

  it("shows a contact as plain text, never a link, and no count it does not have", () => {
    const { container } = render(<ScamReportDetails scam={SCAM} />);

    expect(container.querySelector("a, [href]")).toBeNull();
    expect(screen.queryByText(/Reported by workers/)).toBeNull();
  });

  it("leaves out what the report does not have", () => {
    render(
      <ScamReportDetails
        scam={{ ...SCAM, tactics: [], trigger_phrases: [], details: {}, indicators: [] }}
      />
    );

    expect(screen.getByText("Medium risk")).toBeTruthy();
    expect(screen.queryByText("Tricks it used")).toBeNull();
    expect(screen.queryByText("Words that gave it away")).toBeNull();
    expect(screen.queryByText("It asked for")).toBeNull();
    expect(screen.queryByText("Contacts in the message")).toBeNull();
  });

  it("names a trick the app has no label for instead of showing a key", () => {
    render(<ScamReportDetails scam={{ ...SCAM, tactics: ["new_trick"] }} />);

    expect(screen.getByText("new trick")).toBeTruthy();
  });
});

describe("EntityReportList with a scam report", () => {
  it("names the report as a scam message shared by a worker and not verified, then shows its details", async () => {
    render(<EntityReportList reports={[REPORT]} />);

    expect(screen.getByText("Scam message")).toBeTruthy();
    expect(
      screen.getByText("Shared by a worker after checking a message. Not verified.")
    ).toBeTruthy();
    expect(screen.getByText(/Approved loan of 5,000 PHP/)).toBeTruthy();
    // The details arrive with the scam strings, which are fetched on demand.
    expect(await screen.findByText("send your photos to all your contacts")).toBeTruthy();
  });

  it("shows a report that is not a scam as before, without the scam details", () => {
    const plain: RadarReportSummary = {
      ...REPORT,
      violation_type: "hidden_fees",
      source: "user",
      summary: "Operator charged a worse rate than the one shown.",
      scam: undefined,
    };
    render(<EntityReportList reports={[plain]} />);

    expect(screen.getByText("Hidden fees")).toBeTruthy();
    expect(screen.getByText("Reported by a worker")).toBeTruthy();
    expect(screen.queryByText("Medium risk")).toBeNull();
  });
});
