// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import QuickReplyChips from "@/components/common/QuickReplyChips";

afterEach(cleanup);

const OPTIONS = [
  { id: "sg", label: "Singapore" },
  { id: "au", label: "Australia" },
  { id: "kr", label: "South Korea" },
];

function renderChips(props: Partial<Parameters<typeof QuickReplyChips>[0]> = {}) {
  const onSelect = vi.fn();
  render(
    <QuickReplyChips
      options={OPTIONS}
      onSelect={onSelect}
      groupLabel="Suggested answers"
      {...props}
    />
  );
  return onSelect;
}

describe("QuickReplyChips", () => {
  it("is a named group of buttons", () => {
    renderChips();

    expect(screen.getByRole("group", { name: "Suggested answers" })).toBeTruthy();
    expect(screen.getAllByRole("button").map((button) => button.textContent)).toEqual([
      "Singapore",
      "Australia",
      "South Korea",
    ]);
  });

  it("reports the chip that was tapped", async () => {
    const onSelect = renderChips();

    await userEvent.setup().click(screen.getByRole("button", { name: "Australia" }));

    expect(onSelect).toHaveBeenCalledWith({ id: "au", label: "Australia" });
  });

  it("can be used from the keyboard: Tab to a chip, then Enter or Space", async () => {
    const user = userEvent.setup();
    const onSelect = renderChips();

    await user.tab();
    expect(document.activeElement?.textContent).toBe("Singapore");
    await user.keyboard("{Enter}");
    await user.tab();
    await user.keyboard(" ");

    expect(onSelect.mock.calls.map(([option]) => option.id)).toEqual(["sg", "au"]);
  });

  it("does nothing while disabled, and the buttons say so", async () => {
    const onSelect = renderChips({ disabled: true });

    await userEvent.setup().click(screen.getByRole("button", { name: "Singapore" }));

    expect(onSelect).not.toHaveBeenCalled();
    expect(screen.getAllByRole("button").every((button) => button.hasAttribute("disabled"))).toBe(
      true
    );
  });

  it("marks the chosen chip as pressed only when a choice is being tracked", () => {
    renderChips({ selectedId: "au" });

    expect(screen.getByRole("button", { name: "Australia" }).getAttribute("aria-pressed")).toBe(
      "true"
    );
    expect(screen.getByRole("button", { name: "Singapore" }).getAttribute("aria-pressed")).toBe(
      "false"
    );
  });

  it("leaves aria-pressed off for one-shot replies", () => {
    renderChips();

    expect(screen.getByRole("button", { name: "Singapore" }).hasAttribute("aria-pressed")).toBe(
      false
    );
  });

  it("is at least 44 px tall on a phone", () => {
    renderChips();

    expect(screen.getByRole("button", { name: "Singapore" }).className).toContain("min-h-11");
  });
});
