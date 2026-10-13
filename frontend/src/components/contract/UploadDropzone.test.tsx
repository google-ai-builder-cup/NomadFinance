// @vitest-environment jsdom
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import UploadDropzone from "@/components/contract/UploadDropzone";

afterEach(cleanup);

function renderDropzone(onSelect = vi.fn()) {
  render(<UploadDropzone file={null} onSelect={onSelect} onClear={vi.fn()} />);
  return { onSelect, input: document.querySelector('input[type="file"]') as HTMLInputElement };
}

describe("UploadDropzone", () => {
  it("tells an empty file it is empty before anything is sent", async () => {
    const { onSelect, input } = renderDropzone();

    await userEvent
      .setup()
      .upload(input, new File([], "contract.pdf", { type: "application/pdf" }));

    await waitFor(() => expect(screen.getByRole("alert").textContent).toContain("is empty"));
    expect(onSelect).not.toHaveBeenCalled();
  });

  it("takes a file with something in it", async () => {
    const { onSelect, input } = renderDropzone();

    await userEvent
      .setup()
      .upload(input, new File(["%PDF-1.4"], "contract.pdf", { type: "application/pdf" }));

    await waitFor(() => expect(onSelect).toHaveBeenCalledOnce());
  });
});
