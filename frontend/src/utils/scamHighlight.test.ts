import { describe, expect, it } from "vitest";

import { splitMessage } from "@/utils/scamHighlight";

const joined = (text: string, phrases: string[]) =>
  splitMessage(text, phrases)
    .map((piece) => piece.text)
    .join("");

describe("splitMessage", () => {
  it("gives nothing for an empty message", () => {
    expect(splitMessage("", ["fee"])).toEqual([]);
  });

  it("is one plain piece when there is nothing to highlight", () => {
    expect(splitMessage("Your parcel arrives tomorrow.", [])).toEqual([
      { text: "Your parcel arrives tomorrow.", highlighted: false, token: null },
    ]);
  });

  it("cuts out each phrase and keeps every other character, in order", () => {
    const text = "Pay the processing fee today or the visa slot is cancelled.";

    const pieces = splitMessage(text, ["processing fee", "visa slot is cancelled"]);

    expect(pieces.map((p) => [p.text, p.highlighted])).toEqual([
      ["Pay the ", false],
      ["processing fee", true],
      [" today or the ", false],
      ["visa slot is cancelled", true],
      [".", false],
    ]);
    expect(joined(text, ["processing fee", "visa slot is cancelled"])).toBe(text);
  });

  it("matches without regard to case but shows the text as written", () => {
    const pieces = splitMessage("PAY the Processing Fee now", ["processing fee"]);

    expect(pieces.find((p) => p.highlighted)?.text).toBe("Processing Fee");
  });

  it("highlights a phrase every time it occurs", () => {
    const pieces = splitMessage("send money, then send money again", ["send money"]);

    expect(pieces.filter((p) => p.highlighted)).toHaveLength(2);
  });

  it("merges phrases that overlap or touch into one highlight", () => {
    const pieces = splitMessage("pay the fee today", ["pay the fee", "the fee today"]);

    expect(pieces).toEqual([{ text: "pay the fee today", highlighted: true, token: null }]);
  });

  it("ignores a phrase that is not in the text, and blank ones", () => {
    const text = "Hello there";

    expect(splitMessage(text, ["not here", "", "   "])).toEqual([
      { text, highlighted: false, token: null },
    ]);
  });

  it("treats characters that mean something in a pattern as plain text", () => {
    const text = "Pay (today) [now] $5 + fee? a.b";

    const pieces = splitMessage(text, ["(today)", "[now]", "$5 +", "fee?", "a.b"]);

    expect(pieces.filter((p) => p.highlighted).map((p) => p.text)).toEqual([
      "(today)",
      "[now]",
      "$5 +",
      "fee?",
      "a.b",
    ]);
  });

  it("finds a phrase in Hindi, Nepali and Bengali, and one with an accent", () => {
    for (const [text, phrase] of [
      ["अभी प्रोसेसिंग फ़ीस भरें", "प्रोसेसिंग फ़ीस"],
      ["तुरुन्त शुल्क तिर्नुहोस्", "शुल्क तिर्नुहोस्"],
      ["এখনই ফি দিন", "ফি দিন"],
      ["Pagbabayad ng Bayarín ngayon", "bayarín"],
    ]) {
      expect(
        splitMessage(text, [phrase])
          .find((p) => p.highlighted)
          ?.text.toLowerCase()
      ).toBe(phrase.toLowerCase());
      expect(joined(text, [phrase])).toBe(text);
    }
  });

  it("makes each redaction token its own piece", () => {
    const pieces = splitMessage("Pay to [ACCOUNT] or call [PHONE], see [URL] [EMAIL] [ID].", []);

    expect(pieces.filter((p) => p.token).map((p) => [p.text, p.token])).toEqual([
      ["[ACCOUNT]", "ACCOUNT"],
      ["[PHONE]", "PHONE"],
      ["[URL]", "URL"],
      ["[EMAIL]", "EMAIL"],
      ["[ID]", "ID"],
    ]);
  });

  it("does not treat other bracketed text as a token", () => {
    const pieces = splitMessage("Reply [YES] or [phone]", []);

    expect(pieces).toEqual([{ text: "Reply [YES] or [phone]", highlighted: false, token: null }]);
  });

  it("marks a token inside a highlighted phrase as both", () => {
    const pieces = splitMessage("Pay to [ACCOUNT] today", ["to [ACCOUNT] today"]);

    expect(pieces.find((p) => p.token)).toEqual({
      text: "[ACCOUNT]",
      highlighted: true,
      token: "ACCOUNT",
    });
    expect(
      pieces
        .filter((p) => p.highlighted)
        .map((p) => p.text)
        .join("")
    ).toBe("to [ACCOUNT] today");
  });

  it("keeps the order and length of the text whatever is highlighted", () => {
    const text = "WhatsApp [PHONE] or apply at [URL]. Pay 800 SGD processing fee [ACCOUNT] today!";

    expect(joined(text, ["800 SGD processing fee", "[ACCOUNT] today", "apply at"])).toBe(text);
  });
});
