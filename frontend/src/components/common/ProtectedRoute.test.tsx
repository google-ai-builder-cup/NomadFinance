import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { beforeEach, describe, expect, it, vi } from "vitest";

import ProtectedRoute from "@/components/common/ProtectedRoute";

const auth = vi.hoisted(() => ({ user: null as object | null, loading: false }));

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => auth }));
vi.mock("@/hooks/useI18n", () => ({ useI18n: () => ({ t: (key: string) => key }) }));
// A real <Navigate> only acts in an effect, which a static render never runs; this marker
// shows where it was asked to go.
vi.mock("react-router-dom", async (importOriginal) => ({
  ...(await importOriginal<typeof import("react-router-dom")>()),
  Navigate: ({ to }: { to: string }) => <span data-redirect={to} />,
  Outlet: () => <span data-page="protected" />,
}));

function render(): string {
  return renderToStaticMarkup(
    <MemoryRouter initialEntries={["/dashboard"]}>
      <ProtectedRoute />
    </MemoryRouter>
  );
}

describe("ProtectedRoute", () => {
  beforeEach(() => {
    auth.user = null;
    auth.loading = false;
  });

  it("sends a signed-out visitor to the landing page, not to sign-in", () => {
    const markup = render();

    expect(markup).toContain('data-redirect="/"');
    expect(markup).not.toContain("/sign-in");
    expect(markup).not.toContain('data-page="protected"');
  });

  it("shows the page to a signed-in user", () => {
    auth.user = { uid: "alice" };

    expect(render()).toContain('data-page="protected"');
  });

  it("waits while the saved session is being restored, so a reload does not bounce", () => {
    auth.loading = true;
    const markup = render();

    expect(markup).not.toContain("data-redirect");
    expect(markup).not.toContain('data-page="protected"');
  });
});
