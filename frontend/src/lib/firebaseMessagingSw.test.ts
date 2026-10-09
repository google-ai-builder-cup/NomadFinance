// The push worker (public/firebase-messaging-sw.js) is plain JavaScript that no bundler touches, so
// it is loaded here as the browser would run it, against stand-ins for `self` and the Firebase
// library (NF-FC-022). What this cannot show is the real library calling these hooks: that was
// read in node_modules/@firebase/messaging (index.sw.esm.js, `onPush` and `onNotificationClick`).
import { readFileSync } from "node:fs";
import path from "node:path";

import { describe, expect, it, vi } from "vitest";

const SOURCE = readFileSync(
  path.resolve(__dirname, "../../public/firebase-messaging-sw.js"),
  "utf8"
);
const ORIGIN = "https://app.example";
const CHECKIN = "/coach/checkin/5a202702c922fc9b4fcf?m=30";

interface FakeWindow {
  url: string;
  focus: ReturnType<typeof vi.fn>;
  postMessage: ReturnType<typeof vi.fn>;
}

const windowAt = (url: string, focus = async () => undefined): FakeWindow => ({
  url,
  focus: vi.fn(focus),
  postMessage: vi.fn(),
});

interface ClickEvent {
  notification: { data?: unknown; close: ReturnType<typeof vi.fn> };
  stopImmediatePropagation: ReturnType<typeof vi.fn>;
  waitUntil: (work: Promise<unknown>) => void;
}

function loadWorker(windows: FakeWindow[] = []) {
  const order: string[] = [];
  const handlers = new Map<string, (event: never) => void>();
  let background: ((payload: unknown) => void) | undefined;
  const self = {
    location: { search: "?apiKey=k&projectId=p&messagingSenderId=s&appId=a", origin: ORIGIN },
    addEventListener: (type: string, handler: (event: never) => void) => {
      order.push(`worker:${type}`);
      handlers.set(type, handler);
    },
    registration: { showNotification: vi.fn() },
    clients: {
      matchAll: vi.fn(async () => windows),
      openWindow: vi.fn(async () => undefined),
    },
  };
  const firebase = {
    initializeApp: vi.fn(),
    messaging: () => {
      order.push("library:messaging");
      return { onBackgroundMessage: (callback: typeof background) => (background = callback) };
    },
  };
  new Function("self", "importScripts", "firebase", SOURCE)(self, vi.fn(), firebase);

  return {
    self,
    firebase,
    order,
    background: (payload: unknown) => background?.(payload),
    /** A tap on a notification; resolves when the work the worker started has ended. */
    async tap(data: unknown): Promise<ClickEvent> {
      let work: Promise<unknown> = Promise.resolve();
      const event: ClickEvent = {
        notification: { data, close: vi.fn() },
        stopImmediatePropagation: vi.fn(),
        waitUntil: (promise) => (work = promise),
      };
      handlers.get("notificationclick")?.(event as never);
      await work;
      return event;
    },
  };
}

describe("the worker's start", () => {
  it("starts the Firebase app from its own address, and registers the tap handler before the library creates its own", () => {
    const worker = loadWorker();

    expect(worker.firebase.initializeApp).toHaveBeenCalledWith({
      apiKey: "k",
      projectId: "p",
      messagingSenderId: "s",
      appId: "a",
    });
    // The library's own handler closes a notification it showed and, with no link, opens nothing;
    // it also stops every handler registered after it. So this file's must be first.
    expect(worker.order).toEqual(["worker:notificationclick", "library:messaging"]);
  });
});

describe("a tap on a notification", () => {
  it("opens the link of one the library showed (the whole push is under FCM_MSG)", async () => {
    const worker = loadWorker();

    const event = await worker.tap({ FCM_MSG: { data: { deep_link: CHECKIN } } });

    expect(worker.self.clients.openWindow).toHaveBeenCalledExactlyOnceWith(CHECKIN);
    expect(event.notification.close).toHaveBeenCalledOnce();
    // The library's handler, registered after this one, must not also run.
    expect(event.stopImmediatePropagation).toHaveBeenCalledOnce();
  });

  it("opens the link of one this worker showed itself", async () => {
    const worker = loadWorker();

    await worker.tap({ deep_link: "/radar/alerts" });

    expect(worker.self.clients.openWindow).toHaveBeenCalledExactlyOnceWith("/radar/alerts");
  });

  it("focuses the window that is already open and hands it the link, instead of opening another", async () => {
    const open = windowAt(`${ORIGIN}/dashboard`);
    const worker = loadWorker([open]);

    await worker.tap({ FCM_MSG: { data: { deep_link: CHECKIN } } });

    expect(open.focus).toHaveBeenCalledOnce();
    // It cannot navigate a window it does not control, so the app is told to.
    expect(open.postMessage).toHaveBeenCalledExactlyOnceWith({
      type: "nf-push-click",
      deep_link: CHECKIN,
    });
    expect(worker.self.clients.openWindow).not.toHaveBeenCalled();
  });

  it("ignores a window of another site", async () => {
    const other = windowAt("https://elsewhere.example/dashboard");
    const worker = loadWorker([other]);

    await worker.tap({ deep_link: CHECKIN });

    expect(other.focus).not.toHaveBeenCalled();
    expect(worker.self.clients.openWindow).toHaveBeenCalledExactlyOnceWith(CHECKIN);
  });

  it("opens a new window if the open one cannot be focused", async () => {
    const stuck = windowAt(`${ORIGIN}/dashboard`, async () => {
      throw new Error("not allowed");
    });
    const worker = loadWorker([stuck]);

    await worker.tap({ deep_link: CHECKIN });

    expect(stuck.postMessage).not.toHaveBeenCalled();
    expect(worker.self.clients.openWindow).toHaveBeenCalledExactlyOnceWith(CHECKIN);
  });

  it.each([
    ["no link at all", { FCM_MSG: { data: {} } }],
    ["a link to another site", { deep_link: "https://evil.example/coach/checkin/x" }],
    ["a link that points to another site without a scheme", { deep_link: "//evil.example/x" }],
    ["a link with a control character in it", { deep_link: "/coach/checkin/x\n" }],
    ["a link that is not text", { deep_link: { path: "/dashboard" } }],
  ])("opens the alert feed for %s", async (_name, data) => {
    const worker = loadWorker();

    await worker.tap(data);

    expect(worker.self.clients.openWindow).toHaveBeenCalledExactlyOnceWith("/radar/alerts");
  });

  it("leaves a notification that is none of this app's pushes alone", async () => {
    const worker = loadWorker();

    const event = await worker.tap(undefined);
    await worker.tap({ something: "else" });

    expect(event.stopImmediatePropagation).not.toHaveBeenCalled();
    expect(event.notification.close).not.toHaveBeenCalled();
    expect(worker.self.clients.openWindow).not.toHaveBeenCalled();
  });
});

describe("a push that arrives in the background", () => {
  it("is not shown a second time when it has a notification: the library has shown it", () => {
    const worker = loadWorker();

    worker.background({
      notification: { title: "Day 30 check-in", body: "…" },
      data: { deep_link: CHECKIN },
    });

    expect(worker.self.registration.showNotification).not.toHaveBeenCalled();
  });

  it("is shown by the worker when it carries data only, with the link kept for the tap", () => {
    const worker = loadWorker();

    worker.background({ data: { body: "A business was reported", deep_link: "/radar/alerts" } });

    expect(worker.self.registration.showNotification).toHaveBeenCalledExactlyOnceWith(
      "NomadFinance",
      expect.objectContaining({
        body: "A business was reported",
        data: { deep_link: "/radar/alerts" },
      })
    );
  });
});
