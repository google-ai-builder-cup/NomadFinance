// @vitest-environment jsdom
// What a push does inside the open app (NF-FC-022): a Coach check-in toast that opens its own
// questions, a Radar alert toast as before, and a tap on a system notification that is followed
// with the router.
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import { dismissToast, useToasts } from "@/hooks/useToast";
import { usePushSync } from "@/hooks/useNotifications";

const push = vi.hoisted(() => ({
  onPush: undefined as undefined | ((title: string, body: string, deepLink?: string) => void),
  onClick: undefined as undefined | ((link: string) => void),
  unsubscribe: vi.fn(),
  stopClicks: vi.fn(),
}));

vi.mock("@/lib/messaging", () => ({
  listenForPushes: async (onPush: typeof push.onPush) => {
    push.onPush = onPush;
    return push.unsubscribe;
  },
  listenForPushClicks: (onOpen: typeof push.onClick) => {
    push.onClick = onOpen;
    return push.stopClicks;
  },
  pushPermission: () => "unsupported",
  requestPushToken: async () => null,
}));
vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "worker-1" } }) }));
vi.mock("@/services/notificationService", () => ({
  countUnreadNotifications: async () => 0,
  listNotifications: async () => [],
  markNotificationRead: async () => undefined,
  NOTIFICATIONS_PAGE_SIZE: 50,
}));
vi.mock("@/services/userService", () => ({ saveFcmToken: async () => undefined }));

/** Runs the hook and writes down what it shows: where the router is, and each toast with its button. */
function Probe() {
  usePushSync();
  const { pathname, search } = useLocation();
  const toasts = useToasts();
  return (
    <div>
      <p data-testid="where">{pathname + search}</p>
      <ul>
        {toasts.map((toast) => (
          <li key={toast.id}>
            <span>{toast.messageKey}</span>
            <button type="button" onClick={toast.action?.onClick}>
              {toast.action?.labelKey}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}

async function mount() {
  render(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <Probe />
    </MemoryRouter>
  );
  // The push listener is set once its promise has settled.
  await act(async () => undefined);
}

const where = () => screen.getByTestId("where").textContent;
const shown = () =>
  screen.queryAllByRole("listitem").map((item) => item.querySelector("span")?.textContent);

beforeEach(() => {
  push.onPush = undefined;
  push.onClick = undefined;
  push.unsubscribe.mockClear();
  push.stopClicks.mockClear();
});
afterEach(() => {
  cleanup();
  // The toast store is shared by the whole file; empty it for the next test.
  for (const id of ["toast-1", "toast-2", "toast-3", "toast-4"]) {
    dismissToast(id);
  }
});

describe("a push that arrives while the app is open", () => {
  it("shows a Coach check-in toast whose button opens that check-in", async () => {
    const user = userEvent.setup();
    await mount();

    act(() => push.onPush?.("Day 30 check-in", "…", "/coach/checkin/5a202702c922fc9b4fcf?m=30"));

    expect(shown()).toEqual(["toast.coachCheckin"]);
    await user.click(screen.getByRole("button", { name: "toast.coachCheckinAction" }));
    expect(where()).toBe("/coach/checkin/5a202702c922fc9b4fcf?m=30");
  });

  it("still shows the Radar alert toast for any other push, as before", async () => {
    const user = userEvent.setup();
    await mount();

    act(() => push.onPush?.("New alert", "…", "/radar/entity/some-slug"));

    expect(shown()).toEqual(["radar.alerts.pushToast"]);
    await user.click(screen.getByRole("button", { name: "radar.alerts.pushToastAction" }));
    expect(where()).toBe("/radar/alerts");
  });

  it("shows the Radar alert toast for a push with no link at all", async () => {
    await mount();

    act(() => push.onPush?.("New alert", "…"));

    expect(shown()).toEqual(["radar.alerts.pushToast"]);
  });

  it.each(["https://evil.example/coach/checkin/x", "//evil.example/coach/checkin/x"])(
    "does not follow a check-in link that points outside the app (%s)",
    async (link) => {
      await mount();

      act(() => push.onPush?.("Day 30 check-in", "…", link));

      expect(shown()).toEqual(["radar.alerts.pushToast"]);
    }
  );
});

describe("a tap on a system notification while the app is open", () => {
  it("opens the link the worker posted", async () => {
    await mount();

    act(() => push.onClick?.("/coach/checkin/5a202702c922fc9b4fcf?m=60"));

    expect(where()).toBe("/coach/checkin/5a202702c922fc9b4fcf?m=60");
  });
});

describe("leaving", () => {
  it("stops listening to both", async () => {
    await mount();

    cleanup();

    expect(push.unsubscribe).toHaveBeenCalledTimes(1);
    expect(push.stopClicks).toHaveBeenCalledTimes(1);
  });
});
