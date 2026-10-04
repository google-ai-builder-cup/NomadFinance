import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import RadarAlertsWidget from "@/components/dashboard/RadarAlertsWidget";
import en from "@/i18n/en.json";
import type { AppNotification } from "@/types/notification";

const feed = vi.hoisted(() => ({
  requestedMax: undefined as number | undefined,
  unread: undefined as number | undefined,
  data: [] as AppNotification[],
}));

vi.mock("@/hooks/useNotifications", () => ({
  useNotifications: (max?: number) => {
    feed.requestedMax = max;
    return { isPending: false, isError: false, isSuccess: true, data: feed.data };
  },
  useUnreadNotificationCount: () => ({ data: feed.unread }),
}));
// AlertItem has its own tests' worth of behaviour; the widget's job is what it asks for.
vi.mock("@/components/radar/AlertItem", () => ({
  default: ({ notification }: { notification: AppNotification }) => <p>{notification.title}</p>,
}));
vi.mock("@/hooks/useI18n", () => ({
  useI18n: () => ({
    t: (key: string, values?: Record<string, string | number>) => {
      const text = key
        .split(".")
        .reduce<unknown>((node, part) => (node as Record<string, unknown>)[part], en) as string;
      return text.replace(/{{(\w+)}}/g, (_, name: string) => String(values?.[name] ?? ""));
    },
  }),
}));

function alert(id: string): AppNotification {
  return {
    id,
    type: "radar_alert",
    title: `Alert ${id}`,
    body: "",
    language: "en",
    read: false,
    created_at: { toDate: () => new Date() } as AppNotification["created_at"],
    schema_version: 1,
  };
}

function render(): string {
  return renderToStaticMarkup(
    <MemoryRouter>
      <RadarAlertsWidget />
    </MemoryRouter>
  );
}

describe("RadarAlertsWidget", () => {
  beforeEach(() => {
    feed.requestedMax = undefined;
    feed.unread = undefined;
    feed.data = [alert("a"), alert("b")];
  });

  it("asks for two alerts, not the whole feed", () => {
    render();

    expect(feed.requestedMax).toBe(2);
  });

  it("shows the unread count from the count query, which can exceed the rows shown", () => {
    feed.unread = 7;

    expect(render()).toContain("7");
  });

  it("leaves the unread line out when the count is zero or unavailable", () => {
    feed.unread = undefined;
    const withoutCount = render();
    feed.unread = 0;
    const zero = render();

    expect(withoutCount).toBe(zero);
    expect(withoutCount).toContain("Alert a");
  });
});
