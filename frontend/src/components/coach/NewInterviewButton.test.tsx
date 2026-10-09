// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import NewInterviewButton, { NewInterviewConfirm } from "@/components/coach/NewInterviewButton";
import { useNewInterviewAsk } from "@/hooks/useNewInterviewAsk";
import { loadNamespace } from "@/lib/i18n";

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(cleanup);

const ASK = /closes this one and its answers/;

/** The button and the question wired together the way the chat does it. */
function Wired({ onRestart, restarting }: { onRestart: () => void; restarting?: boolean }) {
  const again = useNewInterviewAsk();
  return (
    <>
      {!again.asking && <NewInterviewButton onClick={again.ask} focusOnMount={again.returned} />}
      {again.asking && (
        <NewInterviewConfirm
          onRestart={onRestart}
          onCancel={again.cancel}
          restarting={restarting}
        />
      )}
    </>
  );
}

describe("starting a new interview", () => {
  it("asks before it closes the interview, because the answers go with it", async () => {
    const onRestart = vi.fn();
    const user = userEvent.setup();
    render(<Wired onRestart={onRestart} />);

    await user.click(screen.getByRole("button", { name: "New interview" }));

    expect(onRestart).not.toHaveBeenCalled();
    expect(screen.getByText(ASK)).toBeTruthy();
    await user.click(screen.getByRole("button", { name: "Yes, start over" }));
    expect(onRestart).toHaveBeenCalledTimes(1);
  });

  it("lets the worker back out, and puts focus back on the button", async () => {
    const onRestart = vi.fn();
    const user = userEvent.setup();
    render(<Wired onRestart={onRestart} />);
    await user.click(screen.getByRole("button", { name: "New interview" }));

    await user.click(screen.getByRole("button", { name: "No, keep going" }));

    expect(onRestart).not.toHaveBeenCalled();
    const button = screen.getByRole("button", { name: "New interview" });
    await vi.waitFor(() => expect(document.activeElement).toBe(button));
  });

  it("moves focus to the question when it asks", async () => {
    const user = userEvent.setup();
    render(<Wired onRestart={vi.fn()} />);

    await user.click(screen.getByRole("button", { name: "New interview" }));

    await vi.waitFor(() => expect(document.activeElement).toBe(screen.getByText(ASK)));
  });

  it("does not offer a second tap while the new interview is starting", async () => {
    const user = userEvent.setup();
    const { rerender } = render(<Wired onRestart={vi.fn()} />);
    await user.click(screen.getByRole("button", { name: "New interview" }));

    rerender(<Wired onRestart={vi.fn()} restarting />);

    const yes = screen.getByRole("button", { name: "Yes, start over" }) as HTMLButtonElement;
    expect(yes.disabled).toBe(true);
  });
});
