// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const firebaseSignOut = vi.hoisted(() => vi.fn());
const clearCoachLocalData = vi.hoisted(() => vi.fn());
const releasePushToken = vi.hoisted(() => vi.fn());
const removeFcmToken = vi.hoisted(() => vi.fn());
const current = vi.hoisted(() => ({ currentUser: null as { uid: string } | null }));

vi.mock("firebase/auth", async (importOriginal) => ({
  ...(await importOriginal<typeof import("firebase/auth")>()),
  signOut: firebaseSignOut,
}));
vi.mock("@/lib/firebase", () => ({ auth: current }));
vi.mock("@/lib/analytics", () => ({
  clearAnalyticsUserProperties: vi.fn(),
  trackLogin: vi.fn(),
}));
vi.mock("@/lib/coachLocalData", () => ({ clearCoachLocalData }));
vi.mock("@/lib/messaging", () => ({ releasePushToken }));
vi.mock("@/services/userService", () => ({ removeFcmToken }));

import { signOut } from "@/services/authService";

function setPermission(permission: NotificationPermission) {
  vi.stubGlobal("Notification", { permission });
}

beforeEach(() => {
  firebaseSignOut.mockReset().mockResolvedValue(undefined);
  clearCoachLocalData.mockReset();
  releasePushToken.mockReset();
  removeFcmToken.mockReset().mockResolvedValue(undefined);
  current.currentUser = { uid: "worker-a" };
  setPermission("default");
});
afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("signOut", () => {
  it("wipes what the Coach keeps on the phone before the person is signed out", async () => {
    const order: string[] = [];
    clearCoachLocalData.mockImplementation(() => order.push("wipe"));
    firebaseSignOut.mockImplementation(async () => void order.push("signed out"));

    await signOut();

    expect(order).toEqual(["wipe", "signed out"]);
  });

  it("takes this browser's push token off the profile before the person is signed out", async () => {
    // Phones are shared: a token left behind keeps the last person's alerts coming to the next.
    setPermission("granted");
    const order: string[] = [];
    releasePushToken.mockImplementation(async () => {
      order.push("released");
      return "token-a";
    });
    removeFcmToken.mockImplementation(async () => void order.push("removed"));
    firebaseSignOut.mockImplementation(async () => void order.push("signed out"));

    await signOut();

    expect(removeFcmToken).toHaveBeenCalledExactlyOnceWith("worker-a", "token-a");
    expect(order).toEqual(["released", "removed", "signed out"]);
  });

  it("does not touch push when it was never turned on in this browser", async () => {
    await signOut();

    expect(releasePushToken).not.toHaveBeenCalled();
    expect(removeFcmToken).not.toHaveBeenCalled();
    expect(firebaseSignOut).toHaveBeenCalledOnce();
  });

  it("signs out even when the push service fails", async () => {
    setPermission("granted");
    releasePushToken.mockRejectedValue(new Error("push service down"));

    await signOut();

    expect(firebaseSignOut).toHaveBeenCalledOnce();
  });

  it("signs out even when removing the token from the profile fails", async () => {
    setPermission("granted");
    releasePushToken.mockResolvedValue("token-a");
    removeFcmToken.mockRejectedValue(new Error("offline"));

    await signOut();

    expect(firebaseSignOut).toHaveBeenCalledOnce();
  });

  it("does not wait for a push service that never answers", async () => {
    vi.useFakeTimers();
    setPermission("granted");
    releasePushToken.mockReturnValue(new Promise(() => undefined));

    const done = signOut();
    await vi.advanceTimersByTimeAsync(3500);
    await done;

    expect(firebaseSignOut).toHaveBeenCalledOnce();
    expect(removeFcmToken).not.toHaveBeenCalled();
  });
});
