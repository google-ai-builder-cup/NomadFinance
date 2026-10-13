// @vitest-environment jsdom
// The window's side of a tap on a system notification (NF-FC-022): the service worker posts the
// link, and only a path inside the app is followed.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { listenForPushClicks, PUSH_CLICK_MESSAGE } from "@/lib/messaging";

vi.mock("@/lib/firebase", () => ({ firebaseApp: {} }));
vi.mock("firebase/messaging", () => ({
  getMessaging: vi.fn(),
  getToken: vi.fn(),
  isSupported: async () => false,
  onMessage: vi.fn(),
}));

type Listener = (event: { data: unknown }) => void;

function fakeServiceWorkerContainer() {
  const listeners = new Set<Listener>();
  const container = {
    addEventListener: vi.fn((_type: string, listener: Listener) => listeners.add(listener)),
    removeEventListener: vi.fn((_type: string, listener: Listener) => listeners.delete(listener)),
    startMessages: vi.fn(),
  };
  Object.defineProperty(navigator, "serviceWorker", { value: container, configurable: true });
  return {
    container,
    post: (data: unknown) => listeners.forEach((listener) => listener({ data })),
  };
}

let original: PropertyDescriptor | undefined;
beforeEach(() => {
  original = Object.getOwnPropertyDescriptor(navigator, "serviceWorker");
});
afterEach(() => {
  if (original) {
    Object.defineProperty(navigator, "serviceWorker", original);
  } else {
    Reflect.deleteProperty(navigator, "serviceWorker");
  }
});

describe("a tap on a notification while the app is open", () => {
  it("follows the link the service worker posts", () => {
    const worker = fakeServiceWorkerContainer();
    const onOpen = vi.fn();
    listenForPushClicks(onOpen);

    worker.post({
      type: PUSH_CLICK_MESSAGE,
      deep_link: "/coach/checkin/5a202702c922fc9b4fcf?m=30",
    });

    expect(onOpen).toHaveBeenCalledExactlyOnceWith("/coach/checkin/5a202702c922fc9b4fcf?m=30");
    // The page may only get its messages once it has been told to start.
    expect(worker.container.startMessages).toHaveBeenCalled();
  });

  it.each([
    { type: "something-else", deep_link: "/dashboard" },
    { type: PUSH_CLICK_MESSAGE, deep_link: "https://evil.example/" },
    { type: PUSH_CLICK_MESSAGE, deep_link: "//evil.example/" },
    { type: PUSH_CLICK_MESSAGE },
    "a string",
    null,
  ])("ignores %j", (message) => {
    const worker = fakeServiceWorkerContainer();
    const onOpen = vi.fn();
    listenForPushClicks(onOpen);

    worker.post(message);

    expect(onOpen).not.toHaveBeenCalled();
  });

  it("stops listening when asked", () => {
    const worker = fakeServiceWorkerContainer();
    const onOpen = vi.fn();
    const stop = listenForPushClicks(onOpen);

    stop();
    worker.post({ type: PUSH_CLICK_MESSAGE, deep_link: "/dashboard" });

    expect(onOpen).not.toHaveBeenCalled();
  });

  it("does nothing in a browser without service workers", () => {
    Reflect.deleteProperty(navigator, "serviceWorker");

    const stop = listenForPushClicks(vi.fn());

    expect(stop).not.toThrow();
  });
});

describe("releasePushToken", () => {
  const getToken = vi.fn();
  const deleteToken = vi.fn();

  async function load(configured = true) {
    vi.resetModules();
    vi.stubEnv("VITE_FIREBASE_MESSAGING_SENDER_ID", configured ? "123" : "");
    vi.stubEnv("VITE_FIREBASE_VAPID_KEY", configured ? "vapid" : "");
    vi.doMock("@/lib/firebase", () => ({ firebaseApp: {} }));
    vi.doMock("firebase/messaging", () => ({
      getMessaging: () => ({}),
      getToken,
      deleteToken,
      isSupported: async () => true,
      onMessage: vi.fn(),
    }));
    return import("@/lib/messaging");
  }

  function browserWith(options: { permission: NotificationPermission; registered: boolean }) {
    vi.stubGlobal("Notification", { permission: options.permission });
    Object.defineProperty(navigator, "serviceWorker", {
      configurable: true,
      value: { getRegistration: async () => (options.registered ? {} : undefined) },
    });
  }

  afterEach(() => {
    getToken.mockReset();
    deleteToken.mockReset();
    vi.unstubAllEnvs();
    vi.unstubAllGlobals();
    vi.doUnmock("firebase/messaging");
  });

  it("forgets this browser's token at FCM and returns it", async () => {
    browserWith({ permission: "granted", registered: true });
    getToken.mockResolvedValue("token-a");
    const { releasePushToken } = await load();

    expect(await releasePushToken()).toBe("token-a");
    expect(deleteToken).toHaveBeenCalledOnce();
  });

  it("does nothing when push was never configured, allowed or registered here", async () => {
    browserWith({ permission: "granted", registered: true });
    expect(await (await load(false)).releasePushToken()).toBeNull();

    browserWith({ permission: "default", registered: true });
    expect(await (await load()).releasePushToken()).toBeNull();

    // No worker of ours: asking Firebase for a token would register a second one.
    browserWith({ permission: "granted", registered: false });
    expect(await (await load()).releasePushToken()).toBeNull();

    expect(getToken).not.toHaveBeenCalled();
    expect(deleteToken).not.toHaveBeenCalled();
  });

  it("never throws", async () => {
    browserWith({ permission: "granted", registered: true });
    getToken.mockRejectedValue(new Error("push service down"));

    expect(await (await load()).releasePushToken()).toBeNull();
  });
});
