// @vitest-environment jsdom
// The history stays true to what the worker just did (NF-SA-018): a new check is a new row, and a
// report changes the row's "reported" marker and the stored check, so both are fetched again.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { SCAM_CHECKS_KEY, useReportCheck, useScamHistory } from "@/hooks/useScamChecks";
import { useScamAnalyze } from "@/hooks/useScamAnalyze";
import { server, setupMockServer } from "@/mocks/server";

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "alice" }, loading: false }) }));
vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

function setup() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const invalidate = vi.spyOn(client, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return { wrapper, invalidate, client };
}

describe("after a check", () => {
  it("refreshes the history, which now has a new newest row", async () => {
    const { wrapper, invalidate } = setup();
    const { result } = renderHook(() => useScamAnalyze(), { wrapper });

    await act(() =>
      result.current.mutateAsync({ input: { kind: "text", text: "Pay the fee" }, language: "en" })
    );

    expect(invalidate).toHaveBeenCalledWith({ queryKey: SCAM_CHECKS_KEY });
  });
});

describe("after a report", () => {
  it("refreshes the history and the stored check", async () => {
    const { wrapper, invalidate } = setup();
    const { result } = renderHook(() => useReportCheck("k_01"), { wrapper });

    await act(() => result.current.mutateAsync({ indicator_ids: [], description: "Pay the fee" }));

    expect(invalidate).toHaveBeenCalledWith({ queryKey: SCAM_CHECKS_KEY });
  });

  it("refetches a history that is on screen, so its row shows the marker", async () => {
    const { wrapper, client } = setup();
    const history = renderHook(() => useScamHistory(), { wrapper });
    await waitFor(() => expect(history.result.current.isSuccess).toBe(true));
    const before = client.getQueryState([...SCAM_CHECKS_KEY, "list"])?.dataUpdatedAt ?? 0;
    const report = renderHook(() => useReportCheck("k_01"), { wrapper });

    await act(() => report.result.current.mutateAsync({ indicator_ids: [], description: "x" }));

    await waitFor(() =>
      expect(client.getQueryState([...SCAM_CHECKS_KEY, "list"])?.dataUpdatedAt).toBeGreaterThan(
        before
      )
    );
  });

  it("does not retry a failed report by itself, so one tap is one request", async () => {
    let calls = 0;
    server.use(
      http.post("*/api/v2/scam/checks/:id/report", () => {
        calls += 1;
        return HttpResponse.json({ code: "internal_error", message: "x" }, { status: 500 });
      })
    );
    const { wrapper } = setup();
    const { result } = renderHook(() => useReportCheck("k_01"), { wrapper });

    await act(() =>
      result.current.mutateAsync({ indicator_ids: [], description: "x" }).catch(() => undefined)
    );

    await waitFor(() => expect(result.current.isError).toBe(true));
    expect(calls).toBe(1);
  });
});
