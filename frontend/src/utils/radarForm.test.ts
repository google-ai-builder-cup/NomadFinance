import { describe, expect, it } from "vitest";

import { ApiError } from "@/services/apiClient";
import type { ReportDraft } from "@/types/radar";
import { buildRequest, reportFailureKey, stepProblem } from "@/utils/radarForm";

const draft: ReportDraft = {
  entityType: "money_transfer_operator",
  entityName: "  Merlion QuickSend ",
  corridorId: "SG-PH",
  hostCountry: null,
  description: "  The receipt showed a higher fee than the app. ",
  language: null,
  files: [],
};

describe("stepProblem", () => {
  it("asks for a type and a name before leaving the first step", () => {
    expect(stepProblem("who", { ...draft, entityType: null })).toBe(
      "radar.report.validation.typeRequired"
    );
    expect(stepProblem("who", { ...draft, entityName: "   " })).toBe(
      "radar.report.validation.nameRequired"
    );
    expect(stepProblem("who", draft)).toBeNull();
  });

  it("needs a corridor for an operator and a country for an employer", () => {
    expect(stepProblem("where", { ...draft, corridorId: null })).toBe(
      "radar.report.validation.locationRequired"
    );
    expect(stepProblem("where", { ...draft, entityType: "employer" })).toBe(
      "radar.report.validation.locationRequired"
    );
    expect(
      stepProblem("where", { ...draft, entityType: "employer", hostCountry: "KR" })
    ).toBeNull();
  });

  it("wants at least 10 characters of description, not counting spaces around it", () => {
    expect(stepProblem("what", { ...draft, description: "  too short " })).toBe(
      "radar.report.validation.descriptionShort"
    );
    expect(stepProblem("what", draft)).toBeNull();
  });
});

describe("buildRequest", () => {
  it("trims text and sends the corridor for an operator", () => {
    expect(buildRequest(draft, "en")).toEqual({
      entity_type: "money_transfer_operator",
      entity_name: "Merlion QuickSend",
      description: "The receipt showed a higher fee than the app.",
      language: "en",
      corridor_id: "SG-PH",
    });
  });

  it("sends the country, not a leftover corridor, for an employer", () => {
    const request = buildRequest(
      { ...draft, entityType: "employer", hostCountry: "HK", language: "tl" },
      "en"
    );
    expect(request.host_country).toBe("HK");
    expect(request.corridor_id).toBeUndefined();
    expect(request.language).toBe("tl");
  });
});

describe("reportFailureKey", () => {
  it("names the reason the backend refused a report", () => {
    expect(reportFailureKey(new ApiError(422, "Please remove personal details (names)."))).toBe(
      "radar.report.errors.personalData"
    );
    expect(reportFailureKey(new ApiError(422, "Could not tell who this report is about."))).toBe(
      "radar.report.errors.entityUnknown"
    );
    expect(reportFailureKey(new ApiError(422, "Unprocessable Content"))).toBe(
      "radar.report.errors.rejected"
    );
  });

  it("uses the AI busy and slow messages and the shared ones for the rest", () => {
    expect(reportFailureKey(new ApiError(503, "busy"))).toBe("radar.report.errors.aiBusy");
    expect(reportFailureKey(new ApiError(504, "slow"))).toBe("radar.report.errors.aiSlow");
    expect(reportFailureKey(new ApiError(429, "wait"))).toBe("errors.tooManyRequests");
    expect(reportFailureKey(new ApiError(0, "Network error"))).toBe("errors.offline");
  });
});
