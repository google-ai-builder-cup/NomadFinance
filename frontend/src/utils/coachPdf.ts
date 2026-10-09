/** The file name a plan's PDF is saved under, as the server names it. */
export function pdfFilename(language: string): string {
  return `nomadfinance-plan-${language}.pdf`;
}

/** Whether this browser can share a PDF file through its share sheet (Android Chrome and Safari
 * can; most desktop browsers cannot). The Share button is shown only where it can. */
export function canSharePdf(nav: Pick<Navigator, "canShare"> | undefined = navigator): boolean {
  try {
    if (typeof nav?.canShare !== "function") {
      return false;
    }
    const probe = new File([new Uint8Array(1)], "plan.pdf", { type: "application/pdf" });
    return nav.canShare({ files: [probe] });
  } catch {
    return false;
  }
}

/** Save `blob` as a download through a link the browser clicks by itself. */
export function savePdf(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.rel = "noopener";
  document.body.appendChild(link);
  link.click();
  link.remove();
  // Give the download a moment to start before the address is released.
  setTimeout(() => URL.revokeObjectURL(url), 10_000);
}

export type ShareOutcome = "shared" | "cancelled" | "blocked" | "unsupported";

/** Open the share sheet with the PDF. `blocked` means the browser refused because the tap was too
 * long ago (the file took a while to make): the caller asks the worker to press again. */
export async function sharePdf(blob: Blob, filename: string, title: string): Promise<ShareOutcome> {
  const file = new File([blob], filename, { type: "application/pdf" });
  if (typeof navigator.share !== "function" || !canSharePdf()) {
    return "unsupported";
  }
  try {
    await navigator.share({ files: [file], title });
    return "shared";
  } catch (error) {
    if (error instanceof DOMException && error.name === "AbortError") {
      return "cancelled";
    }
    if (error instanceof DOMException && error.name === "NotAllowedError") {
      return "blocked";
    }
    return "unsupported";
  }
}
