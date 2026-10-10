import { expect, type Locator, type Page } from "@playwright/test";

import { coachText, QUESTION, type Slot } from "./coachApi";

// The worker's side of the interview, through the screen's own helpers (chips, the amount and
// date fields), shared by the Coach's browser tests (NF-FC-025). Each step names the question it
// answers, the text the screen is expected to send for it, and how to give the answer. The English
// copy is in src/i18n/coach/en.json.

export interface Step {
  slot: Slot;
  /** What the helper writes as the answer: the server reads this text. */
  sent: string;
  give(page: Page): Promise<void>;
}

/** The conversation (not the hidden line that says each finished reply to a screen reader). */
export function conversation(page: Page, language = "en"): Locator {
  return page.getByRole("log", { name: coachText(language, "chat.log") });
}

export function panel(page: Page, language = "en"): Locator {
  return page.getByRole("group", { name: coachText(language, "input.panel") });
}

const chip = (name: string) => async (page: Page) =>
  panel(page).getByRole("button", { name, exact: true }).click();

const field = (label: string, value: string, currency?: string) => async (page: Page) => {
  await panel(page).getByLabel(label, { exact: true }).fill(value);
  if (currency) {
    await panel(page).getByLabel("Currency").selectOption(currency);
  }
  await panel(page).getByRole("button", { name: "Send", exact: true }).click();
};

export const STEPS: readonly Step[] = [
  { slot: "destination_country", sent: "Australia", give: chip("Australia") },
  { slot: "job_type", sent: "Care worker", give: chip("Care worker") },
  {
    slot: "departure_date",
    sent: "2026-12-01",
    give: async (page) => {
      await panel(page).getByLabel("Departure date").fill("2026-12-01");
      await panel(page).getByRole("button", { name: "Send", exact: true }).click();
    },
  },
  {
    slot: "monthly_salary",
    sent: "4200 AUD per month",
    give: field("Amount", "4200"),
  },
  { slot: "dependents", sent: "3", give: field("Number of people", "3") },
  { slot: "remittance_target", sent: "900 AUD per month", give: field("Amount", "900") },
  { slot: "recruitment_fee_paid", sent: "150000 INR", give: field("Amount", "150000", "INR") },
  { slot: "debt_outstanding", sent: "120000 INR", give: field("Amount", "120000", "INR") },
  {
    slot: "debt_interest",
    sent: "3% interest per month",
    give: field("Interest rate (%)", "3"),
  },
  { slot: "savings", sent: "25000 INR", give: field("Amount", "25000", "INR") },
  { slot: "bank_or_wallet", sent: "Bank account", give: chip("Bank account") },
];

/** The coach has asked this question (it is in the conversation). */
export async function expectAsked(page: Page, slot: Slot): Promise<void> {
  await expect(conversation(page).getByText(QUESTION[slot]).last()).toBeVisible();
}

/** Answers the questions from `from` up to (not including) `to`, waiting for each reply. */
export async function answer(page: Page, from: Slot, to: Slot | "review"): Promise<void> {
  const first = STEPS.findIndex((step) => step.slot === from);
  const last = to === "review" ? STEPS.length : STEPS.findIndex((step) => step.slot === to);
  for (const [index, step] of STEPS.slice(first, last).entries()) {
    await step.give(page);
    const next = STEPS[first + index + 1];
    if (next) {
      await expectAsked(page, next.slot);
    }
  }
  if (to === "review") {
    await expect(page.getByRole("heading", { name: "Your answers" })).toBeVisible();
  }
}
