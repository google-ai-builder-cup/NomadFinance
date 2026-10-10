import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import AccountMenu from "@/components/layout/AccountMenu";

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({ user: { displayName: "Lani Ocampo", email: null, phoneNumber: null } }),
}));
vi.mock("@/hooks/useI18n", () => ({ useI18n: () => ({ t: (key: string) => key }) }));
vi.mock("@/services/authService", () => ({ signOut: async () => undefined }));

describe("the account button", () => {
  it("has the initials a worker sees in its name (WCAG 2.5.3, label in name)", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <AccountMenu />
      </MemoryRouter>
    );
    const button = html.slice(html.indexOf("<button"), html.indexOf("</button>"));

    // No `aria-label` standing in for the content: the name is made from the content, which holds
    // the initials and, for a screen reader only, what the button is.
    expect(button).not.toContain("aria-label");
    expect(button).toContain(">LA<");
    expect(button).toContain('class="sr-only">layout.accountMenu<');
  });
});
