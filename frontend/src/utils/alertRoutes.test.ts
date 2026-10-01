import { describe, expect, it } from "vitest";

import type { UserProfile } from "@/types/user";
import { alertRoutes } from "@/utils/alertRoutes";

const profile = (fields: Partial<UserProfile>) => fields as UserProfile;

describe("alertRoutes", () => {
  it("uses the routes chosen in the profile, in route order", () => {
    const chosen = profile({
      host_country: "SG",
      home_country: "PH",
      notification_prefs: { radar_corridors: ["AU-IN", "SG-IN", "XX-YY"] },
    });

    expect(alertRoutes(chosen)).toEqual(["SG-IN", "AU-IN"]);
  });

  it("falls back to the worker's own route", () => {
    expect(alertRoutes(profile({ host_country: "AU", home_country: "PH" }))).toEqual(["AU-PH"]);
  });

  it("treats an empty choice like no choice", () => {
    const empty = profile({
      host_country: "JP",
      home_country: "PH",
      notification_prefs: { radar_corridors: [] },
    });

    expect(alertRoutes(empty)).toEqual(["JP-PH"]);
  });

  it("gives a worker without a surveyed route every route from their host country", () => {
    expect(alertRoutes(profile({ host_country: "SG", home_country: "NP" }))).toEqual([
      "SG-PH",
      "SG-IN",
    ]);
  });

  it("has nothing for a host country without routes, or no profile", () => {
    expect(alertRoutes(profile({ host_country: "KR", home_country: "NP" }))).toEqual([]);
    expect(alertRoutes(undefined)).toEqual([]);
  });
});
