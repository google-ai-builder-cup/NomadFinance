import { renderToStaticMarkup } from "react-dom/server";
import { MemoryRouter } from "react-router-dom";
import { describe, expect, it, vi } from "vitest";

import NotFound from "@/pages/NotFound";

vi.mock("@/hooks/useI18n", () => ({ useI18n: () => ({ t: (key: string) => key }) }));

describe("the page that does not exist", () => {
  it("is a page of its own with a level-1 heading, since no shell supplies one", () => {
    const html = renderToStaticMarkup(
      <MemoryRouter>
        <NotFound />
      </MemoryRouter>
    );

    expect(html).toMatch(/<h1[^>]*>notFound\.title<\/h1>/);
    expect(html).not.toContain("<h2");
  });
});
