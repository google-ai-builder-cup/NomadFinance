// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

import "@/lib/i18n";
import RefreshScore from "@/components/fib/RefreshScore";

const state = vi.hoisted(() => ({
  mutate: vi.fn(),
  value: { isPending: false, isSuccess: false, isError: false, data: undefined, error: null } as {
    isPending: boolean;
    isSuccess: boolean;
    isError: boolean;
    data?: { status: string };
    error: unknown;
  },
}));

vi.mock("@/hooks/useFIB", () => ({
  useRefreshFinancialProfile: () => ({ ...state.value, mutate: state.mutate }),
}));

beforeEach(() => {
  state.mutate.mockClear();
  state.value = {
    isPending: false,
    isSuccess: false,
    isError: false,
    data: undefined,
    error: null,
  };
});
afterEach(cleanup);

describe("RefreshScore", () => {
  it("asks for the score when pressed", async () => {
    render(<RefreshScore />);

    await userEvent.setup().click(screen.getByRole("button", { name: "Work out my score now" }));

    expect(state.mutate).toHaveBeenCalledOnce();
  });

  it("shows it is working and cannot be pressed again meanwhile", () => {
    state.value = { ...state.value, isPending: true };
    render(<RefreshScore />);

    const button = screen.getByRole("button", { name: /Working it out/ });
    expect((button as HTMLButtonElement).disabled).toBe(true);
  });

  it("says plainly when nothing is logged yet", () => {
    state.value = { ...state.value, isSuccess: true, data: { status: "no_data" } };
    render(<RefreshScore />);

    expect(screen.getByRole("status").textContent).toContain(
      "Log some income, bills or savings first"
    );
  });

  it("shows a failure in words, not a key", () => {
    state.value = { ...state.value, isError: true, error: new Error("x") };
    render(<RefreshScore />);

    expect(screen.getByRole("alert").textContent).not.toMatch(/errors\./);
  });
});
