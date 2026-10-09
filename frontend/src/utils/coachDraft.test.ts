// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import { clearDraft, readDraft, writeDraft } from "@/utils/coachDraft";
import { DRAFT_KEY_PREFIX } from "@/utils/coachStorageKeys";

const NOW = Date.parse("2026-10-20T10:00:00Z");
const DAY = 24 * 60 * 60 * 1000;

afterEach(() => localStorage.clear());

describe("drafts", () => {
  it("keeps what was typed for one question of one interview", () => {
    writeDraft("u1", "s1", "income:monthly_salary", { "text.text": "about 4200" }, NOW);

    expect(readDraft("u1", "s1", "income:monthly_salary", NOW)).toEqual({
      "text.text": "about 4200",
    });
  });

  it("offers nothing for another question, interview or person", () => {
    writeDraft("u1", "s1", "income:monthly_salary", { "text.text": "x" }, NOW);

    expect(readDraft("u1", "s1", "obligations:dependents", NOW)).toEqual({});
    expect(readDraft("u1", "s2", "income:monthly_salary", NOW)).toEqual({});
    expect(readDraft("u2", "s1", "income:monthly_salary", NOW)).toEqual({});
  });

  it("merges the fields of several helpers, and drops a field that is emptied", () => {
    writeDraft("u1", "s1", "q", { "money.amount": "4200", "panel.typing": "1" }, NOW);
    writeDraft("u1", "s1", "q", { "money.amount": "" }, NOW);

    expect(readDraft("u1", "s1", "q", NOW)).toEqual({ "panel.typing": "1" });
  });

  it("removes the whole draft when nothing is left", () => {
    writeDraft("u1", "s1", "q", { "text.text": "x" }, NOW);
    writeDraft("u1", "s1", "q", { "text.text": "" }, NOW);

    expect(localStorage.getItem(`${DRAFT_KEY_PREFIX}u1`)).toBeNull();
  });

  it("starts afresh when the question changes", () => {
    writeDraft("u1", "s1", "q1", { "text.text": "old" }, NOW);
    writeDraft("u1", "s1", "q2", { "text.text": "new" }, NOW);

    expect(readDraft("u1", "s1", "q1", NOW)).toEqual({});
    expect(readDraft("u1", "s1", "q2", NOW)).toEqual({ "text.text": "new" });
  });

  it("is not offered after the interview itself would have been abandoned", () => {
    writeDraft("u1", "s1", "q", { "text.text": "x" }, NOW);

    expect(readDraft("u1", "s1", "q", NOW + 14 * DAY)).toEqual({ "text.text": "x" });
    expect(readDraft("u1", "s1", "q", NOW + 14 * DAY + 1)).toEqual({});
  });

  it("does not keep a pasted book", () => {
    writeDraft("u1", "s1", "q", { "text.text": "a".repeat(50_000) }, NOW);

    expect(readDraft("u1", "s1", "q", NOW)["text.text"]).toHaveLength(4_000);
  });

  it("ignores a stored value it cannot read", () => {
    localStorage.setItem(`${DRAFT_KEY_PREFIX}u1`, "{not json");
    expect(readDraft("u1", "s1", "q", NOW)).toEqual({});
    localStorage.setItem(`${DRAFT_KEY_PREFIX}u1`, JSON.stringify({ sessionId: 1 }));
    expect(readDraft("u1", "s1", "q", NOW)).toEqual({});
  });

  it("clears one person's draft only", () => {
    writeDraft("u1", "s1", "q", { "text.text": "x" }, NOW);
    writeDraft("u2", "s9", "q", { "text.text": "y" }, NOW);

    clearDraft("u1");

    expect(readDraft("u1", "s1", "q", NOW)).toEqual({});
    expect(readDraft("u2", "s9", "q", NOW)).toEqual({ "text.text": "y" });
  });
});
