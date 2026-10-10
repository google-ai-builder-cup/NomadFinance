import { describe, expect, it } from "vitest";

import { ApiError } from "@/services/apiClient";
import {
  analysisFromDoc,
  canRetry,
  type ContractProgressDoc,
  failureMessageKey,
  progressView,
  requestFailureKey,
  uploadFailureKey,
} from "@/utils/pipelineProgress";

describe("progressView", () => {
  it("runs the first step while the file is still being sent", () => {
    const view = progressView("uploading", null);

    expect(view.current).toBe("read");
    expect(view.states).toEqual({
      read: "running",
      place: "waiting",
      law: "waiting",
      check: "waiting",
      report: "waiting",
    });
  });

  it("follows the backend step, with every earlier step done", () => {
    const view = progressView("analyzing", { status: "processing", step: "compare" });

    expect(view.current).toBe("check");
    expect(view.states).toMatchObject({ read: "done", law: "done", check: "running" });
    expect(view.states.report).toBe("waiting");
  });

  it.each([
    ["complaint", "report"],
    ["translate", "report"],
    ["detect", "place"],
    ["law", "law"],
  ] as const)("shows backend step %s as screen step %s", (step, screen) => {
    expect(progressView("analyzing", { status: "processing", step }).current).toBe(screen);
  });

  it("treats an uploaded contract waiting for its claim as finding the country", () => {
    expect(progressView("analyzing", { status: "uploaded" }).current).toBe("place");
  });

  it("marks the failed step and keeps its code", () => {
    const doc: ContractProgressDoc = {
      status: "failed",
      error: { step: "compare", code: "gemini_busy" },
    };

    const view = progressView("failed", doc);

    expect(view.current).toBe("check");
    expect(view.states).toMatchObject({ place: "done", check: "failed", report: "waiting" });
    expect(view.failedCode).toBe("gemini_busy");
  });

  it("shows an old failure as a fresh start while a retry runs", () => {
    const doc: ContractProgressDoc = {
      status: "failed",
      error: { step: "compare", code: "gemini_busy" },
    };

    const view = progressView("analyzing", doc, false);

    expect(view.failedCode).toBeNull();
    expect(view.current).toBe("place");
  });

  it("shows this run's failure before its request has answered", () => {
    const doc: ContractProgressDoc = {
      status: "failed",
      error: { step: "compare", code: "gemini_busy" },
    };

    const view = progressView("analyzing", doc, true);

    expect(view.current).toBe("check");
    expect(view.states.check).toBe("failed");
    expect(view.failedCode).toBe("gemini_busy");
  });

  it("puts a failure before any contract exists on the first step", () => {
    const view = progressView("failed", null);

    expect(view.current).toBe("read");
    expect(view.states.read).toBe("failed");
  });

  it("is finished when the document says completed, whatever the request did", () => {
    const view = progressView("failed", { status: "completed" });

    expect(view.current).toBeNull();
    expect(view.failedCode).toBeNull();
  });

  it("treats a completed document from an earlier check as not started", () => {
    const analyzing = progressView("analyzing", { status: "completed" }, false);
    const failed = progressView("failed", { status: "completed" }, false);

    expect(analyzing.current).toBe("place");
    expect(analyzing.states.read).toBe("done");
    expect(failed.current).toBe("place");
    expect(failed.states.place).toBe("failed");
  });
});

describe("failure messages", () => {
  it.each([
    ["gemini_busy", "contract.progress.errors.aiBusy", true],
    ["gemini_unavailable", "contract.progress.errors.aiBusy", true],
    ["gemini_timeout", "contract.progress.errors.aiSlow", true],
    ["internal", "contract.progress.errors.generic", true],
    ["no_terms", "contract.progress.errors.noTerms", false],
    ["not_employment_contract", "contract.progress.errors.notEmploymentContract", false],
    ["no_law_data", "contract.progress.errors.noLawData", false],
    ["poor_legibility", "contract.progress.errors.poorLegibility", false],
  ] as const)("%s: %s, retry %s", (code, key, retry) => {
    expect(failureMessageKey(code)).toBe(key);
    expect(canRetry(code)).toBe(retry);
  });

  it("offers a retry when the reason is unknown (for example the network)", () => {
    expect(failureMessageKey(null)).toBe("contract.progress.errors.generic");
    expect(canRetry(null)).toBe(true);
  });
});

describe("analysisFromDoc", () => {
  const finished: ContractProgressDoc = {
    status: "completed",
    host_country: "SG",
    job_type: "domestic_worker",
    health_score: 31,
    risk_level: "danger",
    clause_counts: { safe: 2, caution: 4, danger: 2 },
    report_languages: ["en", "hi"],
  };

  it("rebuilds the result when the response was lost but the server finished", () => {
    const analysis = analysisFromDoc("C1", finished, "hi");

    expect(analysis).toMatchObject({
      contract_id: "C1",
      health_score: 31,
      risk_level: "danger",
      report_language: "hi",
      complaint_pending: false,
    });
  });

  it("gives nothing for an unfinished contract", () => {
    expect(analysisFromDoc("C1", { ...finished, status: "processing" }, "hi")).toBeNull();
    expect(analysisFromDoc("C1", { status: "completed" }, "hi")).toBeNull();
  });
});

describe("request failure messages", () => {
  it.each([
    [503, "contract.progress.errors.aiBusy"],
    [504, "contract.progress.errors.aiSlow"],
    [502, "contract.progress.errors.generic"],
    [500, "errors.server"],
    [429, "errors.tooManyRequests"],
    [0, "errors.offline"],
  ])("maps HTTP %i to %s", (status, key) => {
    expect(requestFailureKey(new ApiError(status, "detail"))).toBe(key);
  });
});

describe("uploadFailureKey", () => {
  it("says a file with no document in it is not a contract, instead of 'something went wrong'", () => {
    expect(uploadFailureKey(new ApiError(422, "No readable document"))).toBe(
      "contract.upload.errors.notAContract"
    );
  });

  it.each([
    [503, "contract.progress.errors.aiBusy"],
    [504, "contract.progress.errors.aiSlow"],
    [429, "errors.tooManyRequests"],
    [500, "errors.server"],
  ])("leaves a %i to the shared wording", (status, key) => {
    expect(uploadFailureKey(new ApiError(status, "detail"))).toBe(key);
  });
});
