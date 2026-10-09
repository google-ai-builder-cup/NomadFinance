// @vitest-environment jsdom
import { describe, expect, it, vi } from "vitest";

const firebaseSignOut = vi.hoisted(() => vi.fn());
const clearCoachLocalData = vi.hoisted(() => vi.fn());

vi.mock("firebase/auth", async (importOriginal) => ({
  ...(await importOriginal<typeof import("firebase/auth")>()),
  signOut: firebaseSignOut,
}));
vi.mock("@/lib/firebase", () => ({ auth: { currentUser: null } }));
vi.mock("@/lib/analytics", () => ({
  clearAnalyticsUserProperties: vi.fn(),
  trackLogin: vi.fn(),
}));
vi.mock("@/lib/coachLocalData", () => ({ clearCoachLocalData }));

import { signOut } from "@/services/authService";

describe("signOut", () => {
  it("wipes what the Coach keeps on the phone before the person is signed out", async () => {
    const order: string[] = [];
    clearCoachLocalData.mockImplementation(() => order.push("wipe"));
    firebaseSignOut.mockImplementation(async () => void order.push("signed out"));

    await signOut();

    expect(order).toEqual(["wipe", "signed out"]);
  });
});
