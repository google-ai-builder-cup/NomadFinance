import { afterEach, describe, expect, it, vi } from "vitest";

import { copyLetterToClipboard, openPrintableLetter } from "@/utils/complaintActions";

// No jsdom in this project (every other test here is pure-logic, node environment): a fake
// window/document is built by hand instead of pulling in a DOM environment for two functions.
function fakePrintWindow() {
  const headAppended: unknown[] = [];
  const bodyAppended: unknown[] = [];
  const document = {
    title: "",
    createElement: vi.fn(() => ({ textContent: "" })),
    head: { appendChild: vi.fn((el: unknown) => headAppended.push(el)) },
    body: { appendChild: vi.fn((el: unknown) => bodyAppended.push(el)) },
  };
  return {
    document,
    headAppended,
    bodyAppended,
    print: vi.fn(),
    close: vi.fn(),
    focus: vi.fn(),
    onafterprint: null as (() => void) | null,
  };
}

describe("openPrintableLetter", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("returns false without touching a document when the popup is blocked", () => {
    vi.stubGlobal("window", { open: vi.fn(() => null) });

    expect(openPrintableLetter("Dear authority,", "Complaint")).toBe(false);
  });

  it("writes the letter as plain text, titles the window and prints it", () => {
    const fake = fakePrintWindow();
    vi.stubGlobal("window", { open: vi.fn(() => fake) });

    const result = openPrintableLetter("Dear authority,\n\nRegards", "Complaint to SG MOM");

    expect(result).toBe(true);
    expect(fake.document.title).toBe("Complaint to SG MOM");
    expect(fake.headAppended).toHaveLength(1); // the print stylesheet
    expect(fake.bodyAppended).toHaveLength(1);
    expect((fake.bodyAppended[0] as { textContent: string }).textContent).toBe(
      "Dear authority,\n\nRegards"
    );
    expect(fake.focus).toHaveBeenCalledOnce();
    expect(fake.print).toHaveBeenCalledOnce();
  });

  it("closes the window once printing is done", () => {
    const fake = fakePrintWindow();
    vi.stubGlobal("window", { open: vi.fn(() => fake) });

    openPrintableLetter("text", "title");
    fake.onafterprint?.();

    expect(fake.close).toHaveBeenCalledOnce();
  });
});

describe("copyLetterToClipboard", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resolves when the clipboard accepts the text", async () => {
    const writeText = vi.fn().mockResolvedValue(undefined);
    vi.stubGlobal("navigator", { clipboard: { writeText } });

    await expect(copyLetterToClipboard("Dear authority,")).resolves.toBeUndefined();
    expect(writeText).toHaveBeenCalledWith("Dear authority,");
  });

  it("rejects when the browser refuses", async () => {
    const writeText = vi.fn().mockRejectedValue(new Error("denied"));
    vi.stubGlobal("navigator", { clipboard: { writeText } });

    await expect(copyLetterToClipboard("text")).rejects.toThrow("denied");
  });
});
