// @vitest-environment jsdom
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import "@/lib/i18n";
import LiveStats from "@/components/landing/LiveStats";
import type { PublicStats } from "@/types/publicStats";

afterEach(cleanup);

const NONE: PublicStats = {
  workers: null,
  contracts_checked: null,
  radar_reports: null,
  alerts_generated: null,
  scam_messages_checked: null,
  scams_flagged: null,
  coach_plans: null,
  generated_at: "2026-10-15T00:00:00Z",
};

function renderWith(stats: PublicStats) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  client.setQueryData(["public-stats"], stats);
  return render(
    <QueryClientProvider client={client}>
      <LiveStats />
    </QueryClientProvider>
  );
}

describe("LiveStats", () => {
  it("shows only the totals that exist, with their real figures", () => {
    renderWith({
      ...NONE,
      contracts_checked: 7,
      radar_reports: 31,
      alerts_generated: 4,
      scams_flagged: 0,
    });

    expect(screen.getByText("contracts checked against labor law")).toBeTruthy();
    expect(screen.getByText("reports shared with the Radar")).toBeTruthy();
    expect(screen.getByText("corridor alerts raised")).toBeTruthy();
    // A zero is "nothing yet", not a figure to show.
    expect(screen.queryByText("messages flagged as scams")).toBeNull();
  });

  it("stays out when fewer than three totals exist, rather than show a half-empty row", () => {
    const { container } = renderWith({ ...NONE, contracts_checked: 7, radar_reports: 31 });

    expect(container.firstChild).toBeNull();
  });
});
