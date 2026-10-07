// @vitest-environment jsdom
// What a worker sees after a check (NF-SA-016): the verdict card, the explanation under it and a way
// to check another message.
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import ScamResult from "@/components/scam/ScamResult";
import { loadNamespace } from "@/lib/i18n";
import { scamResult } from "@/mocks/scamResult";

beforeAll(async () => {
  await loadNamespace("scam");
});

afterEach(cleanup);

describe("ScamResult", () => {
  it("shows the card, then what the sender wants and what to do now", () => {
    render(<ScamResult result={scamResult("high")} onCheckAnother={() => undefined} />);

    expect(screen.getAllByRole("heading", { level: 2 })[0].textContent).toBe(
      "This looks like a scam"
    );
    expect(screen.getByRole("heading", { name: "What the sender wants" })).toBeTruthy();
    expect(screen.getByRole("heading", { name: "What to do now" })).toBeTruthy();
  });

  it("shows the reassurance and the tip for a message that is not a scam", () => {
    render(<ScamResult result={scamResult("benign")} onCheckAnother={() => undefined} />);

    expect(screen.getByText(/ordinary delivery notice/)).toBeTruthy();
    expect(screen.queryByRole("heading", { name: "What to do now" })).toBeNull();
  });

  it("keeps the verdict and says so when the explanation could not be written", () => {
    render(<ScamResult result={scamResult("noExplainer")} onCheckAnother={() => undefined} />);

    expect(screen.getByRole("meter")).toBeTruthy();
    expect(screen.getByText(/could not write the full explanation/)).toBeTruthy();
  });

  it("still lets a tap on a trick explain itself without the explainer", async () => {
    render(<ScamResult result={scamResult("noExplainer")} onCheckAnother={() => undefined} />);

    await userEvent.click(screen.getByRole("button", { name: "Scaring you" }));

    expect(screen.getByText(/The sender threatens you/)).toBeTruthy();
  });

  it("starts another check when asked", async () => {
    const onCheckAnother = vi.fn();
    render(<ScamResult result={scamResult("high")} onCheckAnother={onCheckAnother} />);

    await userEvent.click(screen.getByRole("button", { name: "Check another message" }));

    expect(onCheckAnother).toHaveBeenCalledOnce();
  });

  it("says when the worker has checked this message before", () => {
    render(
      <ScamResult result={scamResult("high", { cached: true })} onCheckAnother={() => undefined} />
    );

    expect(screen.getByText("You checked this message before.")).toBeTruthy();
  });
});
