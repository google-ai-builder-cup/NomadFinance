// @vitest-environment jsdom
// The plan's PDF (NF-FC-021): fetched through the API with the worker's token, in the app's
// language, kept for the second press, shared only where the phone can share a file.
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { HttpResponse, http } from "msw";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import PdfActions from "@/components/coach/plan/PdfActions";
import { loadNamespace } from "@/lib/i18n";
import { server, setupMockServer } from "@/mocks/server";

const pdf = vi.hoisted(() => ({
  canShare: true,
  save: vi.fn(),
  share: vi.fn(),
}));

vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));
vi.mock("@/utils/coachPdf", () => ({
  canSharePdf: () => pdf.canShare,
  pdfFilename: (language: string) => `nomadfinance-plan-${language}.pdf`,
  savePdf: pdf.save,
  sharePdf: pdf.share,
}));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("coach");
});
beforeEach(() => {
  pdf.canShare = true;
  pdf.save.mockReset();
  pdf.share.mockReset().mockResolvedValue("shared");
});
afterEach(cleanup);

const ID = "5a202702c922fc9b4fcf";

interface Seen {
  auth: string | null;
  language: string | null;
}

function servePdf(): Seen[] {
  const seen: Seen[] = [];
  server.use(
    http.get(`*/api/v2/coach/plans/${ID}.pdf`, ({ request }) => {
      seen.push({
        auth: request.headers.get("Authorization"),
        language: new URL(request.url).searchParams.get("language"),
      });
      return new HttpResponse("%PDF-1.7 plan", {
        headers: {
          "Content-Type": "application/pdf",
          "Content-Disposition": 'attachment; filename="nomadfinance-plan-hi.pdf"',
        },
      });
    })
  );
  return seen;
}

describe("Download", () => {
  it("asks for the PDF with the token and the language, then saves it under its name", async () => {
    const seen = servePdf();
    const user = userEvent.setup();
    render(<PdfActions planId={ID} language="hi" />);

    await user.click(screen.getByRole("button", { name: "Download PDF" }));

    await waitFor(() => expect(pdf.save).toHaveBeenCalledTimes(1));
    expect(seen).toEqual([{ auth: "Bearer test-token", language: "hi" }]);
    const [blob, filename] = pdf.save.mock.calls[0] as [Blob, string];
    expect(filename).toBe("nomadfinance-plan-hi.pdf");
    expect(await blob.text()).toBe("%PDF-1.7 plan");
  });

  it("says the file is being made while it waits, and cannot be pressed twice", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => (release = resolve));
    server.use(
      http.get(`*/api/v2/coach/plans/${ID}.pdf`, async () => {
        await gate;
        return new HttpResponse("%PDF", { headers: { "Content-Type": "application/pdf" } });
      })
    );
    const user = userEvent.setup();
    render(<PdfActions planId={ID} language="en" />);

    await user.click(screen.getByRole("button", { name: "Download PDF" }));

    expect(await screen.findByText(/Making your PDF/)).toBeTruthy();
    expect(
      (screen.getByRole("button", { name: "Download PDF" }) as HTMLButtonElement).disabled
    ).toBe(true);
    release();
    await waitFor(() => expect(pdf.save).toHaveBeenCalled());
    expect(screen.queryByText(/Making your PDF/)).toBeNull();
  });

  it("asks only once for a language, however many times it is saved or shared", async () => {
    const seen = servePdf();
    const user = userEvent.setup();
    render(<PdfActions planId={ID} language="en" />);

    await user.click(screen.getByRole("button", { name: "Download PDF" }));
    await waitFor(() => expect(pdf.save).toHaveBeenCalledTimes(1));
    await user.click(screen.getByRole("button", { name: "Share" }));
    await user.click(screen.getByRole("button", { name: "Download PDF" }));

    await waitFor(() => expect(pdf.save).toHaveBeenCalledTimes(2));
    expect(pdf.share).toHaveBeenCalledTimes(1);
    expect(seen).toHaveLength(1);
  });

  it("asks again when the language changed", async () => {
    const seen = servePdf();
    const user = userEvent.setup();
    const view = render(<PdfActions planId={ID} language="en" />);
    await user.click(screen.getByRole("button", { name: "Download PDF" }));
    await waitFor(() => expect(pdf.save).toHaveBeenCalledTimes(1));

    view.rerender(<PdfActions planId={ID} language="hi" />);
    await user.click(screen.getByRole("button", { name: /PDF/ }));

    await waitFor(() => expect(pdf.save).toHaveBeenCalledTimes(2));
    expect(seen.map((request) => request.language)).toEqual(["en", "hi"]);
  });

  it("shows the failure, and works again when pressed again", async () => {
    let calls = 0;
    server.use(
      http.get(`*/api/v2/coach/plans/${ID}.pdf`, () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({ code: "internal", message: "x" }, { status: 500 })
          : new HttpResponse("%PDF", { headers: { "Content-Type": "application/pdf" } });
      })
    );
    const user = userEvent.setup();
    render(<PdfActions planId={ID} language="en" />);

    await user.click(screen.getByRole("button", { name: "Download PDF" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    expect(pdf.save).not.toHaveBeenCalled();
    await user.click(screen.getByRole("button", { name: "Download PDF" }));
    await waitFor(() => expect(pdf.save).toHaveBeenCalledTimes(1));
    expect(screen.queryByRole("alert")).toBeNull();
  });
});

describe("Share", () => {
  it("is not offered where the phone cannot share a file", () => {
    pdf.canShare = false;

    render(<PdfActions planId={ID} language="en" />);

    expect(screen.queryByRole("button", { name: "Share" })).toBeNull();
    expect(screen.getByRole("button", { name: "Download PDF" })).toBeTruthy();
  });

  it("opens the share sheet with the file and a title", async () => {
    servePdf();
    const user = userEvent.setup();
    render(<PdfActions planId={ID} language="en" />);

    await user.click(screen.getByRole("button", { name: "Share" }));

    await waitFor(() => expect(pdf.share).toHaveBeenCalledTimes(1));
    const [blob, filename, title] = pdf.share.mock.calls[0] as [Blob, string, string];
    expect(await blob.text()).toBe("%PDF-1.7 plan");
    expect(filename).toBe("nomadfinance-plan-en.pdf");
    expect(title).toBe("My 90-day plan");
    expect(pdf.save).not.toHaveBeenCalled();
  });

  it("asks to press again when the phone refused the share after the wait", async () => {
    servePdf();
    pdf.share.mockResolvedValueOnce("blocked");
    const user = userEvent.setup();
    render(<PdfActions planId={ID} language="en" />);

    await user.click(screen.getByRole("button", { name: "Share" }));

    expect(await screen.findByText("Your PDF is ready. Press Share again.")).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Share" }));
    await waitFor(() => expect(pdf.share).toHaveBeenCalledTimes(2));
    expect(screen.queryByText(/Press Share again/)).toBeNull();
  });

  it("saves the file when the phone turns out not to share it", async () => {
    servePdf();
    pdf.share.mockResolvedValueOnce("unsupported");
    const user = userEvent.setup();
    render(<PdfActions planId={ID} language="en" />);

    await user.click(screen.getByRole("button", { name: "Share" }));

    await waitFor(() => expect(pdf.save).toHaveBeenCalledTimes(1));
  });

  it("says nothing when the worker closes the share sheet", async () => {
    servePdf();
    pdf.share.mockResolvedValueOnce("cancelled");
    const user = userEvent.setup();
    render(<PdfActions planId={ID} language="en" />);

    await user.click(screen.getByRole("button", { name: "Share" }));

    await waitFor(() => expect(pdf.share).toHaveBeenCalled());
    expect(screen.queryByRole("alert")).toBeNull();
    expect(screen.queryByText(/Press Share again/)).toBeNull();
    expect(pdf.save).not.toHaveBeenCalled();
  });
});
