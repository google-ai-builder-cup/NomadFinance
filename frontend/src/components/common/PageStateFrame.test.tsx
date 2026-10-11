import { Radar } from "lucide-react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";

import PageStateFrame from "@/components/common/PageStateFrame";

describe("PageStateFrame", () => {
  it("puts the page's own level-1 heading above a loading or failed state", () => {
    const html = renderToStaticMarkup(
      <PageStateFrame pillar="radar" icon={Radar} title="Exploitation Radar">
        <p role="status">Loading</p>
      </PageStateFrame>
    );

    expect(html).toMatch(/<h1[^>]*>Exploitation Radar<\/h1>/);
    expect(html.indexOf("<h1")).toBeLessThan(html.indexOf('role="status"'));
  });
});
