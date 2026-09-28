import { describe, expect, it } from "vitest";

import { ApiError } from "@/services/apiClient";
import { reportFailureKey } from "@/utils/reportLanguage";

describe("reportFailureKey", () => {
  it("tells the worker to check the contract again when the analysis is out of date", () => {
    expect(reportFailureKey(new ApiError(409, "This contract has not been analysed yet."))).toBe(
      "contract.report.switchOutOfDate"
    );
  });

  it("uses the analysis messages for a busy or slow AI service", () => {
    expect(reportFailureKey(new ApiError(503, "busy"))).toBe("contract.progress.errors.aiBusy");
    expect(reportFailureKey(new ApiError(504, "slow"))).toBe("contract.progress.errors.aiSlow");
    expect(reportFailureKey(new ApiError(502, "bad"))).toBe("contract.progress.errors.generic");
  });

  it("does not blame the connection for an answer the backend gave", () => {
    expect(reportFailureKey(new ApiError(404, "No such contract."))).not.toBe("errors.offline");
  });

  it("falls back to the report load error for a failed Firestore read", () => {
    expect(reportFailureKey(new Error("permission-denied"))).toBe(
      "contract.result.reportLoadError"
    );
  });
});
