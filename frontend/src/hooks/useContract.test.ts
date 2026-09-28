import { QueryClient } from "@tanstack/react-query";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { reportPlaceholder, reportQueryOptions, retryReportLoad } from "@/hooks/useContract";
import { ApiError } from "@/services/apiClient";
import { getContractReport, switchReportLanguage } from "@/services/contractService";
import type { ContractReport } from "@/types/contract";

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "u1" } }) }));
vi.mock("@/services/contractService", () => ({
  getContractReport: vi.fn(),
  switchReportLanguage: vi.fn(),
  analyzeContract: vi.fn(),
  uploadContract: vi.fn(),
  watchContractProgress: vi.fn(),
}));

const report = (language: "en" | "hi" | "ne"): ContractReport =>
  ({ language, summary: language, clauses: [] }) as unknown as ContractReport;

const args = (language: "en" | "hi" | "ne" | null, stored: ("en" | "hi" | "ne")[] = ["en"]) => ({
  uid: "u1",
  contractId: "c1",
  language,
  storedLanguages: stored,
});

beforeEach(() => {
  vi.mocked(getContractReport).mockReset();
  vi.mocked(switchReportLanguage).mockReset();
});

describe("reportQueryOptions: where a language comes from", () => {
  it("reads a stored language from Firestore without calling the backend", async () => {
    vi.mocked(getContractReport).mockResolvedValue(report("en"));

    const data = await new QueryClient().fetchQuery(reportQueryOptions(args("en")));

    expect(data?.language).toBe("en");
    expect(getContractReport).toHaveBeenCalledWith("u1", "c1", "en");
    expect(switchReportLanguage).not.toHaveBeenCalled();
  });

  it("asks the backend for a language that is not stored yet", async () => {
    vi.mocked(switchReportLanguage).mockResolvedValue(report("hi"));

    const data = await new QueryClient().fetchQuery(reportQueryOptions(args("hi")));

    expect(data?.language).toBe("hi");
    expect(switchReportLanguage).toHaveBeenCalledWith("c1", "hi");
    expect(getContractReport).not.toHaveBeenCalled();
  });

  it("makes no second request when the worker switches back to a language already seen", async () => {
    vi.mocked(getContractReport).mockResolvedValue(report("en"));
    vi.mocked(switchReportLanguage).mockResolvedValue(report("hi"));
    const client = new QueryClient();

    await client.fetchQuery(reportQueryOptions(args("en")));
    await client.fetchQuery(reportQueryOptions(args("hi")));
    await client.fetchQuery(reportQueryOptions(args("en")));
    await client.fetchQuery(reportQueryOptions(args("hi")));

    expect(getContractReport).toHaveBeenCalledTimes(1);
    expect(switchReportLanguage).toHaveBeenCalledTimes(1);
  });

  it("keeps a stored-but-missing report as null instead of translating it", async () => {
    vi.mocked(getContractReport).mockResolvedValue(null);

    const data = await new QueryClient().fetchQuery(reportQueryOptions(args("en")));

    expect(data).toBeNull();
    expect(switchReportLanguage).not.toHaveBeenCalled();
  });

  it("does not run until there is a contract, a language and a signed-in user", () => {
    expect(reportQueryOptions(args(null)).enabled).toBe(false);
    expect(reportQueryOptions({ ...args("en"), contractId: null }).enabled).toBe(false);
    expect(reportQueryOptions({ ...args("en"), uid: undefined }).enabled).toBe(false);
    expect(reportQueryOptions(args("en")).enabled).toBe(true);
  });
});

describe("retryReportLoad", () => {
  it("never repeats a backend answer by itself: the worker decides", () => {
    expect(retryReportLoad(0, new ApiError(503, "busy"))).toBe(false);
    expect(retryReportLoad(0, new ApiError(0, "Network error"))).toBe(false);
  });

  it("still retries a failed Firestore read once", () => {
    expect(retryReportLoad(0, new Error("unavailable"))).toBe(true);
    expect(retryReportLoad(1, new Error("unavailable"))).toBe(false);
  });

  it("is what the report query uses", () => {
    expect(reportQueryOptions(args("hi")).retry).toBe(retryReportLoad);
  });
});

describe("reportPlaceholder: the report shown while another loads", () => {
  const key = (contractId: string) => ({ queryKey: ["contractReport", "u1", contractId, "en"] });

  it("keeps the previous language of the same contract", () => {
    const previous = report("en");

    expect(reportPlaceholder("c1", previous, key("c1"))).toBe(previous);
  });

  it("never shows another contract's report", () => {
    expect(reportPlaceholder("c1", report("en"), key("OTHER"))).toBeUndefined();
  });

  it("shows nothing when there was no previous query", () => {
    expect(reportPlaceholder("c1", undefined, undefined)).toBeUndefined();
  });
});
