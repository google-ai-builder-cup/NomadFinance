// @vitest-environment jsdom
// What a worker sees for a check (NF-SA-016, NF-SA-018): the verdict card, the explanation under
// it, "Warn other workers" for a scam, and a way to check another message.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render as renderPlain, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import type { ReactElement } from "react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import ScamResult from "@/components/scam/ScamResult";
import { trackScamVerdictViewed } from "@/lib/analytics";
import { loadNamespace } from "@/lib/i18n";
import { scamResult } from "@/mocks/scamResult";

vi.mock("@/lib/analytics", () => ({
  trackScamVerdictViewed: vi.fn(),
  trackScamReported: vi.fn(),
}));

beforeAll(async () => {
  await loadNamespace("scam");
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

// The report button reads and writes through the API and links to Radar.
function render(ui: ReactElement) {
  return renderPlain(
    <QueryClientProvider client={new QueryClient()}>
      <MemoryRouter>{ui}</MemoryRouter>
    </QueryClientProvider>
  );
}

describe("ScamResult", () => {
  it("shows the card, then what the sender wants and what to do now", () => {
    render(<ScamResult result={scamResult("high")} onCheckAnother={() => undefined} />);

    expect(screen.getAllByRole("heading", { level: 2 })[0].textContent).toBe(
      "This looks like a scam"
    );
    expect(screen.getByRole("heading", { name: "What the sender wants" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "What to do now" })).toBeTruthy();
  });

  it("shows the reassurance and the tip for a message that is not a scam", () => {
    render(<ScamResult result={scamResult("benign")} onCheckAnother={() => undefined} />);

    expect(screen.getByText(/ordinary delivery notice/)).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "What to do now" })).toBeNull();
  });

  it("keeps the verdict and says so when the explanation could not be written", () => {
    render(<ScamResult result={scamResult("noExplainer")} onCheckAnother={() => undefined} />);

    expect(screen.getByRole("meter")).toBeTruthy();
    expect(screen.getByText(/could not write the full explanation/)).toBeTruthy();
  });

  it("still lets a tap on a trick explain itself without the explainer", async () => {
    render(<ScamResult result={scamResult("noExplainer")} onCheckAnother={() => undefined} />);

    await userEvent.click(screen.getByRole("button", { name: "Scaring you" }));

    expect(screen.getByText(/The sender threatens you/)).toBeTruthy();
  });

  it("starts another check when asked", async () => {
    const onCheckAnother = vi.fn();
    render(<ScamResult result={scamResult("high")} onCheckAnother={onCheckAnother} />);

    await userEvent.click(screen.getByRole("button", { name: "Check another message" }));

    expect(onCheckAnother).toHaveBeenCalledOnce();
  });

  it("says when the worker has checked this message before", () => {
    render(
      <ScamResult result={scamResult("high", { cached: true })} onCheckAnother={() => undefined} />
    );

    expect(screen.getByText("You checked this message before.")).toBeTruthy();
  });

  it("offers to warn other workers about a scam, and not about a message that is not one", () => {
    const { unmount } = render(
      <ScamResult result={scamResult("high")} onCheckAnother={() => undefined} />
    );
    expect(screen.getByRole("button", { name: "Warn other workers" })).toBeTruthy();
    unmount();

    render(<ScamResult result={scamResult("benign")} onCheckAnother={() => undefined} />);
    expect(screen.queryByRole("button", { name: "Warn other workers" })).toBeNull();
  });

  it("has no check-another button for a stored check, which has its own way on", () => {
    render(<ScamResult result={scamResult("high")} />);

    expect(screen.queryByRole("button", { name: "Check another message" })).toBeNull();
  });

  describe("the verdict_viewed event (NF-SA-022)", () => {
    it("says what the verdict was, once, for a check that has just finished", () => {
      const result = scamResult("high", { cached: false });

      const { rerender } = render(<ScamResult result={result} focusOnMount />);
      rerender(
        <QueryClientProvider client={new QueryClient()}>
          <MemoryRouter>
            <ScamResult result={{ ...result }} focusOnMount />
          </MemoryRouter>
        </QueryClientProvider>
      );

      expect(trackScamVerdictViewed).toHaveBeenCalledTimes(1);
      expect(trackScamVerdictViewed).toHaveBeenCalledWith({
        isScam: true,
        riskLevel: "high",
        scamType: "illegal_recruitment_fee",
        cached: false,
        source: "check",
      });
    });

    it("calls a stored check opened from the history a history view, and a benign one no type", () => {
      render(<ScamResult result={scamResult("benign", { cached: undefined })} />);

      expect(trackScamVerdictViewed).toHaveBeenCalledWith({
        isScam: false,
        riskLevel: "low",
        scamType: null,
        cached: false,
        source: "history",
      });
    });

    it("sends nothing the worker wrote: only the fields of the verdict", () => {
      render(<ScamResult result={scamResult("high")} focusOnMount />);

      const sent = vi.mocked(trackScamVerdictViewed).mock.calls[0][0];
      expect(Object.keys(sent).sort()).toEqual([
        "cached",
        "isScam",
        "riskLevel",
        "scamType",
        "source",
      ]);
      expect(JSON.stringify(sent)).not.toContain(scamResult("high").redacted_text.slice(0, 20));
    });
  });
});
