// @vitest-environment jsdom
// The verdict card for the four mock cases of docs/mocks/scam/ (NF-SA-016): what each shows, that
// colour is never the only signal, and that nothing a stranger wrote is ever treated as HTML or as
// a link.
import { cleanup, render, screen, within } from "@testing-library/react";
import { afterEach, beforeAll, describe, expect, it } from "vitest";

import VerdictCard from "@/components/scam/VerdictCard";
import { loadNamespace, setLanguage } from "@/lib/i18n";
import { scamResult } from "@/mocks/scamResult";

beforeAll(async () => {
  await loadNamespace("scam");
});

afterEach(async () => {
  cleanup();
  await setLanguage("en");
});

describe("a scam judged high risk (mock 1)", () => {
  const result = scamResult("high");

  it("says it looks like a scam, with the meter, the badge and the kind of scam", () => {
    render(<VerdictCard result={result} />);

    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("This looks like a scam");
    const meter = screen.getByRole("meter", { name: "Scam risk" });
    expect(meter.getAttribute("aria-valuetext")).toBe("High risk");
    expect(screen.getByText("High risk")).toBeTruthy();
    expect(screen.getByText("Kind of scam")).toBeTruthy();
    expect(screen.getByText("Illegal recruitment fee", { selector: "strong" })).toBeTruthy();
  });

  it("shows each trick as a button", () => {
    render(<VerdictCard result={result} />);

    expect(screen.getByRole("button", { name: "Pressure to hurry" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "Only a few left" })).toBeTruthy();
    expect(screen.queryByRole("button", { name: "Scaring you" })).toBeNull();
  });

  it("picks out exactly the giveaway wording, bold and underlined, and announces it", () => {
    const { container } = render(<VerdictCard result={result} />);

    const marks = [...container.querySelectorAll("mark")];
    expect(marks.map((mark) => mark.textContent?.replace("Suspicious words: ", ""))).toEqual([
      "processing fee",
      "visa slot is cancelled",
    ]);
    for (const mark of marks) {
      expect(mark.className).toContain("font-bold");
      expect(mark.className).toContain("underline");
      expect(within(mark).getByText("Suspicious words:", { exact: false })).toBeTruthy();
    }
    expect(screen.getByText("Words that gave it away are bold and underlined.")).toBeTruthy();
  });

  it("shows each hidden value as a labelled chip, not as a token", () => {
    render(<VerdictCard result={result} />);

    expect(screen.getByText("account number hidden")).toBeTruthy();
    expect(screen.getByText("phone number hidden")).toBeTruthy();
    expect(screen.queryByText(/\[ACCOUNT\]|\[PHONE\]/)).toBeNull();
  });

  it("lists the contact points with what is wrong with each, and how often they were reported", () => {
    render(<VerdictCard result={result} />);

    expect(screen.getByText("Contacts in the message")).toBeTruthy();
    expect(screen.getByText("6590000001")).toBeTruthy();
    expect(screen.getByText("Reported by workers 5 times")).toBeTruthy();
    expect(screen.getByText("Reported by several workers")).toBeTruthy();
    expect(screen.getByText("sg-careers-visa.example")).toBeTruthy();
    expect(screen.getByText("Copies the real website mom.gov.sg")).toBeTruthy();
  });

  it("gives every warning an icon next to its words", () => {
    render(<VerdictCard result={result} />);

    for (const words of ["Copies the real website mom.gov.sg", "Reported by several workers"]) {
      const badge = screen.getByText(words);
      expect(badge.querySelector("svg[aria-hidden='true']")).toBeTruthy();
    }
    expect(
      screen.getByRole("heading", { level: 2 }).parentElement?.querySelector("svg")
    ).toBeTruthy();
  });

  it("shows what is known about it: the kinds of scam it resembles and the reports on the route", () => {
    render(<VerdictCard result={result} />);

    expect(screen.getByText("Looks like scams we know")).toBeTruthy();
    expect(screen.getAllByText("Illegal recruitment fee").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("Workers on your route sent 7 reports like this one.")).toBeTruthy();
  });

  it("says nothing about being unsure when it is sure", () => {
    render(<VerdictCard result={result} />);

    expect(screen.queryByText(/not fully sure/)).toBeNull();
  });
});

describe("the other scam cases", () => {
  it("shows a medium risk meter with one contact point and no flags (mock 2)", () => {
    render(<VerdictCard result={scamResult("medium")} />);

    expect(screen.getByRole("meter").getAttribute("aria-valuetext")).toBe("Medium risk");
    expect(screen.getByText("Loan app trap", { selector: "strong" })).toBeTruthy();
    expect(screen.getByText("quickloan-ph.example")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Scaring you" })).toBeTruthy();
    expect(screen.getByText("Workers on your route sent 2 reports like this one.")).toBeTruthy();
  });

  it("shows a low risk meter, and says it is not sure when the verdict is shaky (mock 3)", () => {
    render(<VerdictCard result={scamResult("low")} />);

    expect(screen.getByRole("meter").getAttribute("aria-valuetext")).toBe("Low risk");
    expect(screen.getByText(/We are not fully sure about this one/)).toBeTruthy();
    expect(screen.queryByText("Contacts in the message")).toBeNull();
    expect(screen.queryByText(/reports? like this one/)).toBeNull();
  });
});

describe("a message that is not a scam (mock 4)", () => {
  it("is reassuring, with no meter, no kind of scam and no tricks", () => {
    const { container } = render(<VerdictCard result={scamResult("benign")} />);

    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe(
      "This does not look like a scam"
    );
    expect(screen.getByText("No scam found")).toBeTruthy();
    expect(screen.queryByRole("meter")).toBeNull();
    expect(screen.queryByText("Kind of scam")).toBeNull();
    expect(screen.queryByText("How it tries to trick you")).toBeNull();
    expect(container.querySelectorAll("mark")).toHaveLength(0);
    expect(screen.getByText(/your parcel from the post office/)).toBeTruthy();
  });

  it("still shows a flagged contact point if the message has one", () => {
    const result = scamResult("benign", {
      indicators: [
        { id: "aaaa1111", kind: "url", value: "bit.ly", flags: ["shortener"], seen: null },
      ],
    });
    render(<VerdictCard result={result} />);

    expect(screen.getByText("bit.ly")).toBeTruthy();
    expect(screen.getByText("Shortened link: it hides where it really goes")).toBeTruthy();
  });
});

describe("what a stranger wrote is never HTML and never a link", () => {
  it("shows markup in the message as plain text", () => {
    const hostile =
      'Pay now <img src=x onerror="alert(1)"> <script>alert(2)</script> <a href="http://evil.example">here</a>';
    const result = scamResult("high", {
      redacted_text: hostile,
      verdict: { ...scamResult("high").verdict, trigger_phrases: ["Pay now"] },
    });
    const { container } = render(<VerdictCard result={result} />);

    expect(container.querySelector("img")).toBeNull();
    expect(container.querySelector("script")).toBeNull();
    expect(container.textContent).toContain("<script>alert(2)</script>");
    expect(container.textContent).toContain('<a href="http://evil.example">here</a>');
  });

  it("never turns a contact point into a link or a button", () => {
    const { container } = render(<VerdictCard result={scamResult("high")} />);

    expect(container.querySelectorAll("a")).toHaveLength(0);
    expect(container.querySelectorAll("[href]")).toHaveLength(0);
    // The only buttons are the tricks, which explain; none opens or copies a contact.
    const buttons = screen.getAllByRole("button").map((button) => button.textContent);
    expect(buttons).toEqual(["Pressure to hurry", "Only a few left"]);
  });

  it("shows a long unbroken address without letting it push the card wider", () => {
    const value = `${"a".repeat(120)}.example`;
    render(
      <VerdictCard
        result={scamResult("high", {
          indicators: [{ id: "bbbb2222", kind: "url", value, flags: [], seen: null }],
        })}
      />
    );

    expect(screen.getByText(value).className).toContain("break-all");
  });
});

describe("in another language", () => {
  it("shows the card in Hindi, with the type, tricks, flags and counts translated", async () => {
    await setLanguage("hi");
    render(<VerdictCard result={scamResult("high")} />);

    expect(screen.getByRole("heading", { level: 2 }).textContent).toBe("यह स्कैम लगता है");
    expect(screen.getByRole("meter").getAttribute("aria-valuetext")).toBe("ज़्यादा जोखिम");
    expect(screen.getByText("भर्ती की ग़ैरक़ानूनी फ़ीस", { selector: "strong" })).toBeTruthy();
    expect(screen.getByRole("button", { name: "जल्दी करने का दबाव" })).toBeTruthy();
    expect(screen.getByText("असली वेबसाइट mom.gov.sg की नक़ल")).toBeTruthy();
    expect(screen.getByText("कामगारों ने 5 बार बताया")).toBeTruthy();
  });

  it("uses the singular for one report in a language that has one", () => {
    render(<VerdictCard result={scamResult("high", { corridor_report_count: 1 })} />);

    expect(screen.getByText("Workers on your route sent 1 report like this one.")).toBeTruthy();
  });

  it("says '10 or more' at the cap", () => {
    render(<VerdictCard result={scamResult("high", { corridor_report_count: 10 })} />);

    expect(
      screen.getByText("Workers on your route sent 10 or more reports like this one.")
    ).toBeTruthy();
  });

  it("shows a type it has no translation for as readable words, not a key", () => {
    const result = scamResult("high");
    render(
      <VerdictCard
        result={{ ...result, verdict: { ...result.verdict, scam_type: "brand_new_scam" } }}
      />
    );

    expect(screen.getByText("brand new scam", { selector: "strong" })).toBeTruthy();
    expect(screen.queryByText(/result\.type/)).toBeNull();
  });
});
