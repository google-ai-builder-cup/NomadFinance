// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { createMemoryRouter, RouterProvider } from "react-router-dom";
import { afterEach, describe, expect, it, vi } from "vitest";

import RouteError from "@/components/common/RouteError";

vi.mock("@/lib/analytics", () => ({ trackCrash: vi.fn() }));
vi.mock("@/hooks/useI18n", () => ({
  useI18n: () => ({ t: (key: string) => key }),
}));

function Broken({ message }: { message: string }): never {
  throw new TypeError(message);
}

function open(message: string) {
  const router = createMemoryRouter(
    [{ path: "/", element: <Broken message={message} />, errorElement: <RouteError /> }],
    { initialEntries: ["/"] }
  );
  render(<RouterProvider router={router} />);
}

const reload = vi.fn();

afterEach(() => {
  cleanup();
  reload.mockReset();
  vi.restoreAllMocks();
  vi.unstubAllGlobals();
});

describe("RouteError", () => {
  it("loads the page again when a page's code file is gone, because asking again in the same page cannot help", () => {
    vi.stubGlobal("location", { ...window.location, reload });
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    open("Failed to fetch dynamically imported module: /assets/ContractUpload-abc.js");

    fireEvent.click(screen.getByRole("button", { name: "common.retry" }));

    expect(reload).toHaveBeenCalledTimes(1);
  });

  it("only draws the page again after any other crash", () => {
    vi.stubGlobal("location", { ...window.location, reload });
    vi.spyOn(console, "error").mockImplementation(() => undefined);
    open("Cannot read properties of undefined");

    fireEvent.click(screen.getByRole("button", { name: "common.retry" }));

    expect(reload).not.toHaveBeenCalled();
  });
});
