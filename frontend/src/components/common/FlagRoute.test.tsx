import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import FlagGate from "@/components/common/FlagGate";
import FlagRoute from "@/components/common/FlagRoute";

const flag = vi.hoisted(() => ({ enabled: false, isLoading: false }));

vi.mock("@/hooks/useFeatureFlag", () => ({ useFeatureFlag: () => flag }));
vi.mock("@/hooks/useI18n", () => ({ useI18n: () => ({ t: (key: string) => key }) }));
// A real <Navigate> only acts in an effect, which a static render never runs; this marker
// shows where it was asked to go and how.
vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router-dom")>()),
  Navigate: ({ to, replace }: { to: string; replace?: boolean }) => (
    <span data-redirect={to} data-replace={String(replace === true)} />
  ),
}));

// A spy rather than a plain component: the module's code is only "fetched" if it is rendered,
// and the lint rule against counting inside a component is right for real components.
const modulePage = vi.hoisted(() => vi.fn());

function ModulePage() {
  modulePage();
  return <span data-page="module" />;
}

function renderRoute(): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/coach"]}>
      <FlagRoute flag="coach">
        <ModulePage />
      </FlagRoute>
    </MemoryRouter>
  );
}

beforeEach(() => {
  flag.enabled = false;
  flag.isLoading = false;
  modulePage.mockClear();
});

describe("FlagRoute", () => {
  it("sends a user the flag is off for to the dashboard, replacing the history entry", () => {
    const markup = renderRoute();

    expect(markup).toContain('data-redirect="/dashboard"');
    expect(markup).toContain('data-replace="true"');
    expect(markup).not.toContain('data-page="module"');
  });

  it("never renders the module for that user, so its code is never fetched", () => {
    renderRoute();

    expect(modulePage).not.toHaveBeenCalled();
  });

  it("shows the module when the flag is on", () => {
    flag.enabled = true;

    const markup = renderRoute();

    expect(markup).toContain('data-page="module"');
    expect(markup).not.toContain("data-redirect");
  });

  it("shows a skeleton, without redirecting, while the answer is on its way", () => {
    flag.isLoading = true;

    const markup = renderRoute();

    expect(markup).toContain('aria-busy="true"');
    expect(markup).toContain("common.loading");
    expect(markup).not.toContain("data-redirect");
    expect(modulePage).not.toHaveBeenCalled();
  });
});

describe("FlagGate", () => {
  function gate(): string {
    return renderToStaticMarkup(
      <FlagGate flag="scam" loading={<i data-slot="loading" />} fallback={<i data-slot="off" />}>
        <b data-slot="on" />
      </FlagGate>
    );
  }

  it("renders nothing for a module that is off, unless a fallback is given", () => {
    expect(gate()).toBe('<i data-slot="off"></i>');
    expect(renderToStaticMarkup(<FlagGate flag="scam">on</FlagGate>)).toBe("");
  });

  it("renders its children when the flag is on", () => {
    flag.enabled = true;

    expect(gate()).toBe('<b data-slot="on"></b>');
  });

  it("renders the loading slot, not the off slot, until the answer arrives", () => {
    flag.isLoading = true;

    expect(gate()).toBe('<i data-slot="loading"></i>');
  });
});
