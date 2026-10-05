import { describe, expect, it } from "vitest";

import bn from "@/i18n/bn.json";
import en from "@/i18n/en.json";
import hi from "@/i18n/hi.json";
import id from "@/i18n/id.json";
import ne from "@/i18n/ne.json";
import tl from "@/i18n/tl.json";

function leaves(node: unknown, prefix = ""): Record<string, string> {
  if (typeof node === "string") {
    return { [prefix]: node };
  }
  return Object.entries(node as Record<string, unknown>).reduce<Record<string, string>>(
    (all, [key, value]) => ({ ...all, ...leaves(value, prefix ? `${prefix}.${key}` : key) }),
    {}
  );
}

const english = leaves(en);
const placeholders = (text: string) => (text.match(/{{\w+}}/g) ?? []).sort();

describe.each([
  ["hi", hi],
  ["tl", tl],
  ["id", id],
  ["ne", ne],
  ["bn", bn],
])("%s locale", (_code, locale) => {
  const translated = leaves(locale);

  it("has every key English has, and no others", () => {
    expect(Object.keys(translated).sort()).toEqual(Object.keys(english).sort());
  });

  it("has no empty text", () => {
    expect(Object.entries(translated).filter(([, text]) => text.trim() === "")).toEqual([]);
  });

  it("keeps the same {{placeholders}} as English in every string", () => {
    const mismatched = Object.entries(translated).filter(
      ([key, text]) => placeholders(text).join() !== placeholders(english[key]).join()
    );
    expect(mismatched.map(([key]) => key)).toEqual([]);
  });
});
