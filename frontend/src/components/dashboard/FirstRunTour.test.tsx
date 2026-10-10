// @vitest-environment jsdom
// The first-run tour (NF-HR-002): shown once, to a worker who has a new module, skippable at every
// step and from the keyboard, and never again after it was seen or skipped.
import { act, cleanup, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import FirstRunTour from "@/components/dashboard/FirstRunTour";
import i18n, { loadNamespace, setLanguage } from "@/lib/i18n";
import { axeViolations, rawKeysShown } from "@/mocks/axe";
import { LANGUAGE_CODES } from "@/types/enums";
import { hasSeenTour, markTourSeen } from "@/utils/firstRunTour";

const state = vi.hoisted(() => ({
  uid: "alice" as string | undefined,
  flags: { scam: true, coach: true },
  isLoading: false,
}));

vi.mock("@/hooks/useAuth", () => ({
  useAuth: () => ({
    user: state.uid === undefined ? null : { uid: state.uid },
    loading: false,
  }),
}));
vi.mock("@/hooks/useFeatureFlag", () => ({
  useFeatureFlags: () => ({ flags: state.flags, isLoading: state.isLoading }),
}));

beforeAll(async () => {
  await loadNamespace("coach");
});
beforeEach(() => {
  localStorage.clear();
  state.uid = "alice";
  state.flags = { scam: true, coach: true };
  state.isLoading = false;
});
afterEach(async () => {
  cleanup();
  document.body.style.overflow = "";
  await act(async () => void (await setLanguage("en")));
  vi.restoreAllMocks();
});

const dialog = () => screen.queryByRole("dialog");

describe("when it appears", () => {
  it("opens on the first step for a worker with a new module who has not seen it", () => {
    render(<FirstRunTour />);

    const tour = within(screen.getByRole("dialog", { name: "What is new in NomadFinance" }));
    expect(tour.getByText("Step 1 of 3")).toBeTruthy();
    expect(tour.getByRole("heading", { name: "Check a message before you act" })).toBeTruthy();
  });

  it("does not open for a worker no module is on for", () => {
    state.flags = { scam: false, coach: false };

    render(<FirstRunTour />);

    expect(dialog()).toBeNull();
  });

  it("does not open while the flags are still on their way, or without a signed-in worker", () => {
    state.isLoading = true;
    const loading = render(<FirstRunTour />);
    expect(dialog()).toBeNull();
    loading.unmount();

    state.isLoading = false;
    state.uid = undefined;
    render(<FirstRunTour />);
    expect(dialog()).toBeNull();
  });

  it("does not open for a worker who has seen it", () => {
    markTourSeen("alice");

    render(<FirstRunTour />);

    expect(dialog()).toBeNull();
  });

  it("is per worker: another account on the same browser still sees it", () => {
    markTourSeen("bob");

    render(<FirstRunTour />);

    expect(dialog()).not.toBeNull();
  });

  it("does not nag when the browser cannot remember that it was shown", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => {
      throw new Error("blocked");
    });

    render(<FirstRunTour />);

    expect(dialog()).toBeNull();
  });

  it.each([
    [{ scam: true, coach: false }, "Step 1 of 2", "Check a message before you act"],
    [{ scam: false, coach: true }, "Step 1 of 2", "Plan before you leave"],
  ])("introduces only the modules that are on: %j", (flags, step, heading) => {
    state.flags = flags;

    render(<FirstRunTour />);

    expect(screen.getByText(step)).toBeTruthy();
    expect(screen.getByRole("heading", { name: heading })).toBeTruthy();
  });
});

describe("walking through it", () => {
  it("goes forward and back, and finishes with 'Got it'", async () => {
    const user = userEvent.setup();
    render(<FirstRunTour />);

    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "Plan before you leave" })).toBeTruthy();
    expect(screen.getByText("Step 2 of 3")).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Back" }));
    expect(screen.getByRole("heading", { name: "Check a message before you act" })).toBeTruthy();

    await user.click(screen.getByRole("button", { name: "Next" }));
    await user.click(screen.getByRole("button", { name: "Next" }));
    expect(screen.getByRole("heading", { name: "All in one place" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Skip" })).toBeNull();

    await user.click(screen.getByRole("button", { name: "Got it" }));

    expect(dialog()).toBeNull();
    expect(hasSeenTour("alice")).toBe(true);
  });

  it("has no Back on the first step", () => {
    render(<FirstRunTour />);

    expect(screen.queryByRole("button", { name: "Back" })).toBeNull();
  });
});

describe("leaving it", () => {
  it.each([
    [
      "the Skip button",
      async (user: ReturnType<typeof userEvent.setup>) => {
        await user.click(screen.getByRole("button", { name: "Skip" }));
      },
    ],
    [
      "the close button",
      async (user: ReturnType<typeof userEvent.setup>) => {
        await user.click(screen.getByRole("button", { name: "Close the tour" }));
      },
    ],
    [
      "the Escape key",
      async (user: ReturnType<typeof userEvent.setup>) => {
        await user.keyboard("{Escape}");
      },
    ],
  ])("%s ends it for good", async (_how, leave) => {
    const user = userEvent.setup();
    const view = render(<FirstRunTour />);

    await leave(user);

    expect(dialog()).toBeNull();
    expect(hasSeenTour("alice")).toBe(true);
    view.unmount();
    render(<FirstRunTour />);
    expect(dialog()).toBeNull();
  });

  it("is ended by a tap outside the panel, and not by a tap inside it", async () => {
    const user = userEvent.setup();
    render(<FirstRunTour />);

    await user.click(screen.getByRole("heading", { name: "Check a message before you act" }));
    expect(dialog()).not.toBeNull();

    await user.click(dialog()?.parentElement as HTMLElement);
    expect(dialog()).toBeNull();
  });
});

describe("using it from the keyboard", () => {
  it("puts focus in the panel, keeps Tab inside it and hands focus back", async () => {
    const user = userEvent.setup();
    const opener = document.createElement("button");
    document.body.append(opener);
    opener.focus();

    const view = render(<FirstRunTour />);
    expect(document.activeElement).toBe(dialog());

    // Close, Skip, Next: Tab from the last wraps to the first, Shift+Tab from the first wraps back.
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close the tour" }));
    await user.tab({ shift: true });
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Next" }));
    await user.tab();
    expect(document.activeElement).toBe(screen.getByRole("button", { name: "Close the tour" }));

    await user.keyboard("{Escape}");
    expect(document.activeElement).toBe(opener);
    view.unmount();
    opener.remove();
  });

  it("stops the page behind it from scrolling, and lets it scroll again", async () => {
    const user = userEvent.setup();
    render(<FirstRunTour />);
    expect(document.body.style.overflow).toBe("hidden");

    await user.keyboard("{Escape}");

    expect(document.body.style.overflow).toBe("");
  });
});

describe("in the six languages", () => {
  it.each(LANGUAGE_CODES)("shows no raw key in %s, on any step, and passes axe", async (code) => {
    const user = userEvent.setup();
    await act(async () => void (await setLanguage(code)));
    const view = render(<FirstRunTour />);

    for (let step = 0; step < 3; step += 1) {
      expect(rawKeysShown(view.container.ownerDocument.body), `${code} step ${step}`).toEqual([]);
      expect(await axeViolations(view.container.ownerDocument.body)).toEqual([]);
      if (step < 2) {
        await user.click(screen.getAllByRole("button").at(-1) as HTMLElement);
      }
    }
    expect(i18n.resolvedLanguage).toBe(code);
  });
});
