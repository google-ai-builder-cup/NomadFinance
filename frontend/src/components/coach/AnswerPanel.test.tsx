// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import AnswerPanel from "@/components/coach/AnswerPanel";
import i18n, { loadNamespace, setLanguage } from "@/lib/i18n";
import type { CoachSlot, CoachStage } from "@/types/coach";

beforeAll(async () => {
  await loadNamespace("coach");
});
afterEach(cleanup);

function renderPanel(
  stage: CoachStage,
  slot: CoachSlot | null,
  options: { slots?: Partial<Record<CoachSlot, unknown>>; busy?: boolean } = {}
) {
  const onSend = vi.fn();
  render(
    <AnswerPanel
      stage={stage}
      slot={slot}
      slots={options.slots ?? { destination_country: "AU" }}
      busy={options.busy ?? false}
      onSend={onSend}
    />
  );
  return onSend;
}

const field = (name: string) => screen.getByLabelText(name) as HTMLInputElement;
const send = () => screen.getByRole("button", { name: "Send" });

describe("chips", () => {
  it("send the words on the chip, as typed text", async () => {
    const onSend = renderPanel("intro", "destination_country");

    await userEvent.setup().click(screen.getByRole("button", { name: "South Korea" }));

    expect(onSend).toHaveBeenCalledWith("South Korea");
  });

  it("use the shared job names for the seven kinds of work", () => {
    renderPanel("intro", "job_type");

    const chips = within(screen.getByRole("group", { name: "Quick answers" })).getAllByRole(
      "button"
    );

    expect(chips.map((chip) => chip.textContent)).toEqual([
      "Domestic worker",
      "Factory worker",
      "Care worker",
      "Plantation or farm worker",
      "Construction worker",
      "Working holiday",
      "Other",
    ]);
  });

  it("are locked while a reply arrives", () => {
    renderPanel("intro", "destination_country", { busy: true });

    expect((screen.getByRole("button", { name: "Singapore" }) as HTMLButtonElement).disabled).toBe(
      true
    );
  });
});

describe("the amount helper", () => {
  it("writes pay as one sentence in the host currency, per month by default", async () => {
    const onSend = renderPanel("income", "monthly_salary");
    const user = userEvent.setup();

    expect(field("Currency").value).toBe("AUD");
    expect(screen.getByRole("button", { name: "Per month" }).getAttribute("aria-pressed")).toBe(
      "true"
    );
    await user.type(field("Amount"), "4,200");
    await user.click(send());

    expect(onSend).toHaveBeenCalledWith("4200 AUD per month");
  });

  it("takes another currency and another period", async () => {
    const onSend = renderPanel("income", "monthly_salary");
    const user = userEvent.setup();

    await user.selectOptions(field("Currency"), "INR");
    await user.click(screen.getByRole("button", { name: "Per week" }));
    await user.type(field("Amount"), "5000.5");
    await user.click(send());

    expect(onSend).toHaveBeenCalledWith("5000.5 INR per week");
  });

  it("starts with the money the worker already used", () => {
    renderPanel("debt", "debt_outstanding", {
      slots: {
        destination_country: "AU",
        monthly_salary: { amount: 18000, currency: "INR", period: "month" },
      },
    });

    expect(field("Currency").value).toBe("INR");
  });

  it("asks a total for a debt: no period, and one tap for none", async () => {
    const onSend = renderPanel("debt", "debt_outstanding");
    const user = userEvent.setup();

    expect(screen.queryByRole("button", { name: "Per month" })).toBeNull();
    await user.type(field("Amount"), "120000");
    await user.click(send());
    await user.click(screen.getByRole("button", { name: "None (0)" }));

    expect(onSend).toHaveBeenNthCalledWith(1, "120000 AUD");
    expect(onSend).toHaveBeenNthCalledWith(2, "None (0)");
  });

  it("refuses pay of zero or no number, and says why, without sending", async () => {
    const onSend = renderPanel("income", "monthly_salary");
    const user = userEvent.setup();

    await user.click(send());
    expect(screen.getByRole("alert").textContent).toBe(
      "Enter an amount above zero, for example 2500."
    );
    await user.type(field("Amount"), "0");
    await user.click(send());

    expect(onSend).not.toHaveBeenCalled();
    expect(field("Amount").getAttribute("aria-invalid")).toBe("true");
  });

  it("accepts a zero for a debt", async () => {
    const onSend = renderPanel("debt", "debt_outstanding");
    const user = userEvent.setup();

    await user.type(field("Amount"), "0");
    await user.click(send());

    expect(onSend).toHaveBeenCalledWith("0 AUD");
  });

  it("does not send while a reply is arriving", async () => {
    const onSend = renderPanel("income", "monthly_salary", { busy: true });
    const user = userEvent.setup();

    await user.type(field("Amount"), "100");
    await user.keyboard("{Enter}");

    expect(onSend).not.toHaveBeenCalled();
    expect((send() as HTMLButtonElement).disabled).toBe(true);
  });
});

describe("the other helpers", () => {
  it("send a whole number of people, and refuse more than 20", async () => {
    const onSend = renderPanel("obligations", "dependents");
    const user = userEvent.setup();

    await user.type(field("Number of people"), "25");
    await user.click(send());
    expect(onSend).not.toHaveBeenCalled();
    await user.clear(field("Number of people"));
    await user.type(field("Number of people"), "3");
    await user.click(send());

    expect(onSend).toHaveBeenCalledWith("3");
  });

  it("send an interest rate with its period", async () => {
    const onSend = renderPanel("debt", "debt_interest");
    const user = userEvent.setup();

    await user.type(field("Interest rate (%)"), "3");
    await user.click(screen.getByRole("button", { name: "Per year" }));
    await user.click(send());

    expect(onSend).toHaveBeenCalledWith("3% interest per year");
  });

  it("send the date as YYYY-MM-DD, or that the worker does not know yet", async () => {
    const onSend = renderPanel("intro", "departure_date");
    const user = userEvent.setup();

    await user.click(send());
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.change(field("Departure date"), { target: { value: "2026-12-01" } });
    await user.click(send());
    await user.click(screen.getByRole("button", { name: "I do not know yet" }));

    expect(onSend).toHaveBeenNthCalledWith(1, "2026-12-01");
    expect(onSend).toHaveBeenNthCalledWith(2, "I do not know yet");
  });
});

describe("typing instead", () => {
  it("switches to a text box, sends on Enter, and goes back to the chips", async () => {
    const onSend = renderPanel("intro", "destination_country");
    const user = userEvent.setup();

    await user.click(screen.getByRole("button", { name: "Type my own answer" }));
    await user.type(
      screen.getByLabelText("Your answer", { selector: "textarea" }),
      "I will go to Dubai{Enter}"
    );

    expect(onSend).toHaveBeenCalledWith("I will go to Dubai");
    await user.click(screen.getByRole("button", { name: "Use quick answers" }));
    expect(screen.getByRole("button", { name: "Singapore" })).toBeTruthy();
  });

  it("adds a line on Shift+Enter instead of sending", async () => {
    const onSend = renderPanel("intro", "destination_country");
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Type my own answer" }));

    await user.type(
      screen.getByLabelText("Your answer", { selector: "textarea" }),
      "one{Shift>}{Enter}{/Shift}two"
    );

    expect(onSend).not.toHaveBeenCalled();
    expect(
      (screen.getByLabelText("Your answer", { selector: "textarea" }) as HTMLTextAreaElement).value
    ).toBe("one\ntwo");
  });

  it("does not cut a long answer: it says so and holds the send button", async () => {
    const onSend = renderPanel("review", null);
    const user = userEvent.setup();
    await user.click(screen.getByRole("button", { name: "Type my own answer" }));
    const box = screen.getByLabelText("Your answer", {
      selector: "textarea",
    }) as HTMLTextAreaElement;

    await user.click(box);
    await user.paste("a".repeat(1001));

    expect(box.value).toHaveLength(1001);
    expect(screen.getByRole("alert").textContent).toContain("Too long");
    expect((send() as HTMLButtonElement).disabled).toBe(true);
    await user.keyboard("{Enter}");
    expect(onSend).not.toHaveBeenCalled();
  });

  it("keeps the text box open while a reply arrives, so the phone's keyboard stays up", async () => {
    renderPanel("intro", null, { busy: true });

    const box = screen.getByLabelText("Your answer", {
      selector: "textarea",
    }) as HTMLTextAreaElement;

    expect(box.disabled).toBe(false);
    expect((screen.getByRole("button", { name: "Send" }) as HTMLButtonElement).disabled).toBe(true);
  });

  it("goes back to the chips when the question changes", async () => {
    const user = userEvent.setup();
    const onSend = vi.fn();
    const { rerender } = render(
      <AnswerPanel
        stage="intro"
        slot="destination_country"
        slots={{}}
        busy={false}
        onSend={onSend}
      />
    );
    await user.click(screen.getByRole("button", { name: "Type my own answer" }));

    rerender(<AnswerPanel stage="intro" slot="job_type" slots={{}} busy={false} onSend={onSend} />);

    expect(screen.getByRole("button", { name: "Care worker" })).toBeTruthy();
  });
});

describe("every language", () => {
  const CASES: Array<[CoachStage, CoachSlot | null]> = [
    ["intro", "destination_country"],
    ["intro", "job_type"],
    ["intro", "departure_date"],
    ["income", "monthly_salary"],
    ["obligations", "dependents"],
    ["debt", "debt_outstanding"],
    ["debt", "debt_interest"],
    ["savings", "bank_or_wallet"],
    ["review", null],
  ];

  it.each(["hi", "tl", "id", "ne", "bn"])(
    "shows translated words, never a key, in %s",
    async (language) => {
      await setLanguage(language);
      try {
        for (const [stage, slot] of CASES) {
          const { container, unmount } = render(
            <AnswerPanel stage={stage} slot={slot} slots={{}} busy={false} onSend={vi.fn()} />
          );
          const text = container.textContent ?? "";
          expect(text, `${stage}/${slot}`).not.toMatch(
            /\b(chat|stage|input|home|confirmed)\.[A-Za-z_.]+/
          );
          expect(text.trim(), `${stage}/${slot}`).not.toBe("");
          unmount();
        }
      } finally {
        await setLanguage("en");
        expect(i18n.resolvedLanguage).toBe("en");
      }
    }
  );
});
