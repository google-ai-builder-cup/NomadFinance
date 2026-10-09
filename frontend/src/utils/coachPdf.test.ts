// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";

import { canSharePdf, pdfFilename, savePdf, sharePdf } from "@/utils/coachPdf";

afterEach(() => {
  vi.restoreAllMocks();
  vi.useRealTimers();
  Object.defineProperty(navigator, "share", { value: undefined, configurable: true });
  Object.defineProperty(navigator, "canShare", { value: undefined, configurable: true });
});

function browserThatShares(share: (data: ShareData) => Promise<void>, can = true) {
  Object.defineProperty(navigator, "canShare", { value: () => can, configurable: true });
  Object.defineProperty(navigator, "share", { value: share, configurable: true });
}

const blob = new Blob(["%PDF-1.7"], { type: "application/pdf" });

describe("the file name", () => {
  it("is the server's", () => {
    expect(pdfFilename("hi")).toBe("nomadfinance-plan-hi.pdf");
  });
});

describe("whether the phone can share a file", () => {
  it("needs canShare to accept a PDF", () => {
    browserThatShares(async () => undefined);
    expect(canSharePdf()).toBe(true);
  });

  it.each([
    ["has no canShare", undefined],
    ["refuses files", () => false],
  ])("is false when the browser %s", (_label, canShare) => {
    Object.defineProperty(navigator, "canShare", { value: canShare, configurable: true });
    expect(canSharePdf()).toBe(false);
  });

  it("is false when canShare throws", () => {
    Object.defineProperty(navigator, "canShare", {
      value: () => {
        throw new TypeError("no");
      },
      configurable: true,
    });
    expect(canSharePdf()).toBe(false);
  });
});

describe("saving the file", () => {
  it("clicks a link that downloads it under its name, then lets the address go", () => {
    vi.useFakeTimers();
    const created = vi.fn(() => "blob:plan");
    const revoked = vi.fn();
    Object.assign(URL, { createObjectURL: created, revokeObjectURL: revoked });
    const clicked: HTMLAnchorElement[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (
      this: HTMLAnchorElement
    ) {
      clicked.push(this);
    });

    savePdf(blob, "nomadfinance-plan-en.pdf");

    expect(created).toHaveBeenCalledWith(blob);
    expect(clicked[0].download).toBe("nomadfinance-plan-en.pdf");
    expect(clicked[0].getAttribute("href")).toBe("blob:plan");
    expect(document.querySelector("a[download]")).toBeNull();
    expect(revoked).not.toHaveBeenCalled();
    vi.advanceTimersByTime(10_000);
    expect(revoked).toHaveBeenCalledWith("blob:plan");
  });
});

describe("sharing the file", () => {
  it("shares the PDF itself and says so", async () => {
    const share = vi.fn(async (_data: ShareData) => undefined);
    browserThatShares(share);

    expect(await sharePdf(blob, "plan.pdf", "My plan")).toBe("shared");
    const data = share.mock.calls[0][0];
    expect(data.files?.[0].name).toBe("plan.pdf");
    expect(data.files?.[0].type).toBe("application/pdf");
    expect(data.title).toBe("My plan");
  });

  it("calls closing the share sheet cancelling, not a failure", async () => {
    browserThatShares(async () => {
      throw new DOMException("closed", "AbortError");
    });

    expect(await sharePdf(blob, "plan.pdf", "t")).toBe("cancelled");
  });

  it("calls a refusal for a tap that was too long ago 'blocked', so the worker presses again", async () => {
    browserThatShares(async () => {
      throw new DOMException("no gesture", "NotAllowedError");
    });

    expect(await sharePdf(blob, "plan.pdf", "t")).toBe("blocked");
  });

  it("is unsupported where files cannot be shared", async () => {
    browserThatShares(async () => undefined, false);

    expect(await sharePdf(blob, "plan.pdf", "t")).toBe("unsupported");
  });

  it("is unsupported when the share fails for another reason", async () => {
    browserThatShares(async () => {
      throw new TypeError("bad");
    });

    expect(await sharePdf(blob, "plan.pdf", "t")).toBe("unsupported");
  });
});
