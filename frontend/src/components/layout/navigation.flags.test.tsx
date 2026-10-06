import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import BottomNav from "@/components/layout/BottomNav";
import { MODULE_ITEMS, PILLAR_ITEMS, visibleNavItems } from "@/components/layout/navItems";
import Sidebar from "@/components/layout/Sidebar";
import type { FeatureFlags } from "@/types/flags";

const state = vi.hoisted(() => ({ flags: { coach: false, scam: false } as FeatureFlags }));

vi.mock("@/hooks/useFeatureFlag", () => ({
  useFeatureFlags: () => ({ flags: state.flags, isLoading: false }),
}));
vi.mock("@/hooks/useI18n", () => ({ useI18n: () => ({ t: (key: string) => key }) }));

const OFF: FeatureFlags = { coach: false, scam: false };

function render(node: JSX.Element): string {
  return renderToStaticMarkup(<MemoryRouter>{node}</MemoryRouter>);
}

beforeEach(() => {
  state.flags = OFF;
});

describe("visibleNavItems", () => {
  it("is exactly the v1.0 five while every flag is off", () => {
    const items = visibleNavItems(OFF).map(({ to }) => to);

    expect(items).toEqual(["/dashboard", "/remittance", "/contract", "/radar", "/identity"]);
  });

  it("adds only the modules that are on, after the v1.0 five", () => {
    expect(visibleNavItems({ coach: true, scam: false }).map(({ to }) => to)).toContain("/coach");
    expect(visibleNavItems({ coach: true, scam: false }).map(({ to }) => to)).not.toContain(
      "/scam-check"
    );
    expect(
      visibleNavItems({ coach: true, scam: true })
        .slice(-2)
        .map(({ to }) => to)
    ).toEqual(["/coach", "/scam-check"]);
  });

  it("keeps the modules out of the pillar list that the landing page and dashboard read", () => {
    const pillarPaths = PILLAR_ITEMS.map(({ to }) => to);

    for (const { to } of MODULE_ITEMS) {
      expect(pillarPaths).not.toContain(to);
    }
    expect(PILLAR_ITEMS).toHaveLength(4);
  });
});

describe.each([
  ["Sidebar", () => render(<Sidebar />)],
  ["BottomNav", () => render(<BottomNav />)],
])("%s", (_name, markup) => {
  it("has no entry for a module whose flag is off", () => {
    const html = markup();

    expect(html).not.toContain('href="/coach"');
    expect(html).not.toContain('href="/scam-check"');
    expect(html).toContain('href="/dashboard"');
    expect(html).toContain('href="/identity"');
  });

  it("has an entry for each module that is on, and only those", () => {
    state.flags = { coach: false, scam: true };

    const html = markup();

    expect(html).toContain('href="/scam-check"');
    expect(html).toContain("nav.scamCheck");
    expect(html).not.toContain('href="/coach"');
  });
});

describe("BottomNav layout", () => {
  const renderAt = (path: string) =>
    renderToStaticMarkup(
      <MemoryRouter initialEntries={[path]}>
        <BottomNav />
      </MemoryRouter>
    );

  it("keeps the v1.0 five-column layout, with every label showing, while the flags are off", () => {
    const html = renderAt("/dashboard");

    expect(html).toContain("grid-cols-5");
    expect(html).not.toContain("grid-template-columns");
    expect(html).not.toContain("sr-only");
  });

  it("with a module on, shows only the active tab's label, in a wider column", () => {
    state.flags = { coach: true, scam: true };

    const html = renderAt("/coach");

    expect(html).not.toContain("grid-cols-5");
    expect(html).toContain("grid-template-columns:1fr 1fr 1fr 1fr 1fr 1.7fr 1fr");
    // The other six labels are still in the page, for screen readers.
    expect(html.match(/class="sr-only"/g)).toHaveLength(6);
    expect(html).toContain('class="max-w-full truncate">nav.coach');
  });

  it("with a module on and no tab active, every label is for screen readers only", () => {
    state.flags = { coach: true, scam: false };

    const html = renderAt("/profile");

    expect(html.match(/class="sr-only"/g)).toHaveLength(6);
    expect(html).not.toContain("truncate");
  });
});
