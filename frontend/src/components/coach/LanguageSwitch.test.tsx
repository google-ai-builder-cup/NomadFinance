// @vitest-environment jsdom
import { act, cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import LanguageSwitch from "@/components/coach/LanguageSwitch";
import i18n, { loadNamespace, setLanguage } from "@/lib/i18n";
import { getSessionLanguage, clearSessionLanguage } from "@/lib/languages";

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(async () => {
  cleanup();
  clearSessionLanguage();
  await act(async () => void (await setLanguage("en")));
});

const select = () => screen.getByRole("combobox") as HTMLSelectElement;

describe("the coach's language switch", () => {
  it("offers the six languages by their own names, with the current one chosen", () => {
    render(<LanguageSwitch />);

    expect([...select().options].map((o) => o.textContent)).toEqual([
      "English",
      "हिन्दी",
      "Tagalog",
      "Bahasa Indonesia",
      "नेपाली",
      "বাংলা",
    ]);
    expect(select().value).toBe("en");
    expect(screen.getByText("Coach language")).toBeTruthy();
  });

  it("changes the whole app's language and remembers it for this tab only", async () => {
    render(<LanguageSwitch />);

    await userEvent.setup().selectOptions(select(), "hi");

    await vi.waitFor(() => expect(i18n.resolvedLanguage).toBe("hi"));
    expect(getSessionLanguage()).toBe("hi");
  });

  it("shows the current language when the app's language is changed elsewhere", async () => {
    render(<LanguageSwitch />);

    await act(async () => void (await setLanguage("bn")));

    expect(select().value).toBe("bn");
  });
});
