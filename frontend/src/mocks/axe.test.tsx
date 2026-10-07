// @vitest-environment jsdom
// The accessibility helper itself (NF-SA-019). A check that cannot fail proves nothing, so this
// shows that it does fail on the faults it exists to find.
import { cleanup, render } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { axeViolations, rawKeysShown } from "@/mocks/axe";

afterEach(cleanup);

describe("axeViolations", () => {
  it("passes a page that is fine", async () => {
    const { container } = render(
      <main>
        <h1>Title</h1>
        <button type="button">Save</button>
        <label>
          Name <input type="text" />
        </label>
      </main>
    );

    expect(await axeViolations(container)).toEqual([]);
  });

  it("fails a button with no name, and says which rule, how bad, and where", async () => {
    const { container } = render(<button type="button" className="icon-only" />);

    const found = await axeViolations(container);

    expect(found).toHaveLength(1);
    expect(found[0]).toMatch(/^button-name \[critical\]/);
    expect(found[0]).toContain("icon-only");
  });

  it("fails an input with no label and an image with no text alternative", async () => {
    const { container } = render(
      <div>
        <input type="text" />
        <img src="/x.png" />
      </div>
    );

    const rules = (await axeViolations(container)).map((line) => line.split(" ")[0]);

    expect(rules).toEqual(expect.arrayContaining(["label", "image-alt"]));
  });

  it("fails a dialog with no name and a list that holds something that is not an item", async () => {
    const { container } = render(
      <div>
        <div role="dialog" aria-modal="true" />
        <ul>
          <div>not an item</div>
        </ul>
      </div>
    );

    const rules = (await axeViolations(container)).map((line) => line.split(" ")[0]);

    expect(rules).toEqual(expect.arrayContaining(["aria-dialog-name", "list"]));
  });

  it("holds back a less serious finding unless asked for it", async () => {
    // Skipping from an h1 to an h3 is moderate: it is not in the tracker's bar, but can be seen.
    const { container } = render(
      <main>
        <h1>Title</h1>
        <h3>Skipped a level</h3>
      </main>
    );

    expect(await axeViolations(container)).toEqual([]);
    expect((await axeViolations(container, "moderate")).join("\n")).toMatch(/heading-order/);
  });

  it("does not judge what only a real browser can: contrast", async () => {
    const { container } = render(
      <p style={{ color: "#eee", background: "#fff" }}>Faint grey on white</p>
    );

    expect(await axeViolations(container, "minor")).toEqual([]);
  });
});

describe("rawKeysShown", () => {
  it("finds an i18n key shown as it is, as text and as an accessible name", () => {
    const { container } = render(
      <div>
        <p>result.risk.high</p>
        <button type="button" aria-label="report.sheet.close" />
      </div>
    );

    expect(rawKeysShown(container)).toEqual([
      "result.risk.high",
      'aria-label="report.sheet.close"',
    ]);
  });

  it("leaves alone words, addresses and numbers a message may hold", () => {
    const { container } = render(
      <div>
        <p>Pay 800 SGD to mom.gov.sg.verify-now.com today</p>
        <p>quickloan-ph.example</p>
        <p>Illegal recruitment fee</p>
        <p>6590000001</p>
      </div>
    );

    expect(rawKeysShown(container)).toEqual([]);
  });
});
