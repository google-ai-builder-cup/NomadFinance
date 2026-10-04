/**
 * Opens a blank window, writes the letter into it as plain text and calls `print()` (NF-P2-013).
 * No PDF library: the worker picks "Save as PDF" in the browser's own print dialog. The window
 * closes itself once printing is done or cancelled (`onafterprint`).
 *
 * Not opened with the `noopener` feature: it makes `window.open` return null in every browser
 * (Chrome, Firefox, Safari), so the code could not tell a blocked pop-up from a window it had
 * opened, showed "allow pop-ups" and left an empty tab behind (NF-P4-002). The window only ever
 * holds our own blank page, so the link back to this page is cut right after opening instead.
 *
 * Returns:
 *   False when the popup was blocked (`window.open` returned null) — nothing else to clean up.
 */
export function openPrintableLetter(text: string, title: string): boolean {
  const printWindow = window.open("", "_blank");
  if (printWindow === null) {
    return false;
  }
  printWindow.opener = null;
  printWindow.document.title = title;
  const style = printWindow.document.createElement("style");
  style.textContent =
    "body { font-family: system-ui, sans-serif; white-space: pre-wrap; " +
    "line-height: 1.6; padding: 2.5rem; max-width: 680px; margin: 0 auto; }";
  printWindow.document.head.appendChild(style);
  // textContent, never innerHTML: the letter is plain text, not markup to render.
  const body = printWindow.document.createElement("div");
  body.textContent = text;
  printWindow.document.body.appendChild(body);
  printWindow.onafterprint = () => printWindow.close();
  printWindow.focus();
  printWindow.print();
  return true;
}

/** Copies the letter to the clipboard. Rejects when the browser refuses (no permission, no API). */
export async function copyLetterToClipboard(text: string): Promise<void> {
  await navigator.clipboard.writeText(text);
}
