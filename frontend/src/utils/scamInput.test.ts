// @vitest-environment jsdom
import { afterEach, describe, expect, it } from "vitest";

import {
  checkMessage,
  clearSharedMessage,
  countChars,
  isSubmittable,
  MAX_MESSAGE_CHARS,
  messageFromShare,
  peekSharedMessage,
  stashSharedMessage,
} from "@/utils/scamInput";

afterEach(() => sessionStorage.clear());

describe("checkMessage", () => {
  it("trims, then accepts up to the limit", () => {
    expect(checkMessage("  hello  ")).toEqual({ ok: true, text: "hello" });
    expect(checkMessage("a".repeat(MAX_MESSAGE_CHARS)).ok).toBe(true);
  });

  it("refuses an empty message and one over the limit, and never cuts", () => {
    expect(checkMessage("   \n ")).toEqual({ ok: false, problem: "empty" });
    expect(checkMessage("a".repeat(MAX_MESSAGE_CHARS + 1))).toEqual({
      ok: false,
      problem: "tooLong",
    });
  });

  it("counts characters the way the backend does, not UTF-16 units", () => {
    const emoji = "😀".repeat(MAX_MESSAGE_CHARS);
    expect(countChars(emoji)).toBe(MAX_MESSAGE_CHARS);
    expect(checkMessage(emoji).ok).toBe(true);
  });
});

describe("isSubmittable", () => {
  it("is the same gate for text and screenshots", () => {
    expect(isSubmittable({ kind: "text", text: "pay now" })).toBe(true);
    expect(isSubmittable({ kind: "text", text: " " })).toBe(false);
    const png = new File(["x"], "chat.png", { type: "image/png" });
    expect(isSubmittable({ kind: "screenshot", file: png })).toBe(true);
    expect(isSubmittable({ kind: "screenshot", file: new File([], "empty.png") })).toBe(false);
  });
});

describe("messageFromShare", () => {
  const read = (query: string) => messageFromShare(new URLSearchParams(query));

  it("takes the shared text", () => {
    expect(read("text=Pay%20800%20SGD%20today")).toBe("Pay 800 SGD today");
  });

  it("joins title, text and link, and drops a part another part already contains", () => {
    expect(
      read("title=Offer&text=Pay%20now%20https%3A%2F%2Fx.example&url=https%3A%2F%2Fx.example")
    ).toBe("Offer\nPay now https://x.example");
    expect(read("title=Pay%20now&text=Pay%20now")).toBe("Pay now");
  });

  it("is empty when nothing was shared", () => {
    expect(read("")).toBe("");
    expect(read("text=%20%20")).toBe("");
  });
});

describe("a shared message kept for the tab", () => {
  it("is found until cleared", () => {
    stashSharedMessage("?text=hello");
    expect(peekSharedMessage()).toBe("hello");
    expect(peekSharedMessage()).toBe("hello");
    clearSharedMessage();
    expect(peekSharedMessage()).toBe("");
  });

  it("keeps nothing when nothing was shared", () => {
    stashSharedMessage("");
    expect(sessionStorage.length).toBe(0);
  });

  it("expires, so a phone that is passed on does not show it", () => {
    stashSharedMessage("?text=hello", 1_000);
    expect(peekSharedMessage(1_000 + 10 * 60 * 1000)).toBe("hello");
    expect(peekSharedMessage(1_000 + 10 * 60 * 1000 + 1)).toBe("");
  });

  it("ignores a damaged entry", () => {
    sessionStorage.setItem("nomadfinance.sharedMessage", "{not json");
    expect(peekSharedMessage()).toBe("");
  });
});
