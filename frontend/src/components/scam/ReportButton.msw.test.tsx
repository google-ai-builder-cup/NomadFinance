// @vitest-environment jsdom
// "Warn other workers" against the mock API (NF-SA-018): the real button, sheet, hook, service and
// API client run, and only the backend's answers come from docs/mocks/scam/.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type JsonBodyType } from "msw";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import ReportButton from "@/components/scam/ReportButton";
import { trackScamReported } from "@/lib/analytics";
import { loadNamespace } from "@/lib/i18n";
import { jsonMocks } from "@/mocks/files";
import { server, setupMockServer } from "@/mocks/server";
import { scamResult } from "@/mocks/scamResult";
import type { ScamIndicator, ScamResultView } from "@/types/scam";
import { MAX_REPORT_CHARS } from "@/utils/scamReport";

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "alice" }, loading: false }) }));
vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

vi.mock("@/lib/analytics", () => ({ trackScamReported: vi.fn() }));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("scam");
});

afterEach(() => {
  cleanup();
  vi.clearAllMocks();
});

interface Sent {
  path: string;
  json: { indicator_ids: string[]; description: string };
}

/** Answers the report route with a mock file and records what the sheet sent. */
function answerWith(mockName: string, sent: Sent[] = [], gate?: Promise<void>): Sent[] {
  const mock = jsonMocks.get(mockName);
  if (mock?.status === undefined) {
    throw new Error(`No single-response mock ${mockName}`);
  }
  server.use(
    http.post("*/api/v2/scam/checks/:id/report", async ({ request }) => {
      sent.push({
        path: new URL(request.url).pathname,
        json: (await request.json()) as Sent["json"],
      });
      await gate;
      return HttpResponse.json(mock.body as JsonBodyType, {
        status: mock.status,
        headers: mock.headers,
      });
    })
  );
  return sent;
}

function renderButton(result: ScamResultView = scamResult("high")) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter>
        <ReportButton result={result} />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const opener = () => screen.getByRole("button", { name: "Warn other workers" });
const dialog = () => screen.getByRole("dialog");
const sheet = () => within(dialog());
const textBox = () => sheet().getByLabelText("The message other workers will see");
const send = () => sheet().getByRole("button", { name: /^Send warning$|^Sending/ });

async function openSheet() {
  await userEvent.click(opener());
}

describe("the button", () => {
  it("is offered for a scam and not for a message that is not one", () => {
    const { unmount } = renderButton();
    expect(opener()).toBeTruthy();
    unmount();

    renderButton(scamResult("benign"));
    expect(screen.queryByRole("button")).toBeNull();
  });
});

describe("the confirmation sheet", () => {
  it("shows exactly what other workers will see, before anything is sent", async () => {
    const sent = answerWith("scam/report-01-created.json");
    renderButton();

    await openSheet();

    expect(sheet().getByRole("heading", { name: "Warn other workers" })).toBeTruthy();
    // The kind of scam, the message as it will be shown, and each contact with a tick.
    expect(sheet().getByText("Illegal recruitment fee", { selector: "strong" })).toBeTruthy();
    expect((textBox() as HTMLTextAreaElement).value).toBe(scamResult("high").redacted_text);
    const ticks = sheet().getAllByRole("checkbox") as HTMLInputElement[];
    expect(ticks).toHaveLength(2);
    expect(ticks.every((tick) => tick.checked)).toBe(true);
    expect(sheet().getByText("6590000001")).toBeTruthy();
    expect(sheet().getByText("sg-careers-visa.example")).toBeTruthy();
    // And what the worker needs to know about it.
    expect(sheet().getByText(/anonymous and not verified/)).toBeTruthy();
    expect(sheet().getByText(/Take out any name you see/)).toBeTruthy();
    expect(sent).toHaveLength(0);
  });

  it("shows a contact as plain text, never a link", async () => {
    renderButton();

    await openSheet();

    expect(dialog().querySelector("a, [href]")).toBeNull();
  });

  it("moves the keyboard into the sheet, and back to the button when it closes", async () => {
    renderButton();
    await openSheet();
    expect(document.activeElement).toBe(dialog());

    await userEvent.keyboard("{Escape}");

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(document.activeElement).toBe(opener());
  });

  it("closes on Cancel and on the close button, and sends nothing", async () => {
    const sent = answerWith("scam/report-01-created.json");
    renderButton();

    await openSheet();
    await userEvent.click(sheet().getByRole("button", { name: "Cancel" }));
    expect(screen.queryByRole("dialog")).toBeNull();

    await openSheet();
    await userEvent.click(sheet().getByRole("button", { name: "Close" }));
    expect(screen.queryByRole("dialog")).toBeNull();
    expect(sent).toHaveLength(0);
  });

  it("keeps Tab inside the sheet", async () => {
    renderButton();
    await openSheet();
    const buttons = sheet().getAllByRole("button");
    buttons[buttons.length - 1].focus();

    await userEvent.tab();
    expect(dialog().contains(document.activeElement)).toBe(true);

    await userEvent.tab({ shift: true });
    await userEvent.tab({ shift: true });
    expect(dialog().contains(document.activeElement)).toBe(true);
  });

  it("says so when the message has no contact in it", async () => {
    renderButton(scamResult("high", { indicators: [] }));

    await openSheet();

    expect(sheet().getByText(/No phone number, link or address was found/)).toBeTruthy();
    expect(sheet().queryByRole("checkbox")).toBeNull();
  });

  it("starts with ten of twelve contacts ticked and will not take an eleventh", async () => {
    const many: ScamIndicator[] = Array.from({ length: 12 }, (_, index) => ({
      id: `c${index}`,
      kind: "phone",
      value: `+65 9000 00${String(index).padStart(2, "0")}`,
      flags: [],
      seen: null,
    }));
    renderButton(scamResult("high", { indicators: many }));

    await openSheet();

    const ticks = sheet().getAllByRole("checkbox") as HTMLInputElement[];
    expect(ticks.filter((tick) => tick.checked)).toHaveLength(10);
    expect(ticks[10].disabled).toBe(true);
    expect(sheet().getByText(/up to 10 contacts/)).toBeTruthy();

    await userEvent.click(ticks[0]);
    expect((sheet().getAllByRole("checkbox")[10] as HTMLInputElement).disabled).toBe(false);
  });
});

describe("the text", () => {
  it("cannot be sent empty", async () => {
    renderButton();
    await openSheet();

    await userEvent.clear(textBox());

    expect((send() as HTMLButtonElement).disabled).toBe(true);
  });

  it("counts its characters and is held at 1,000", async () => {
    renderButton();
    await openSheet();

    fireEvent.change(textBox(), { target: { value: "a".repeat(MAX_REPORT_CHARS + 10) } });

    expect((textBox() as HTMLTextAreaElement).value).toHaveLength(MAX_REPORT_CHARS);
    expect(sheet().getByText("1000 / 1000")).toBeTruthy();
  });
});

describe("sending", () => {
  it("sends exactly what the sheet shows: the edited text and the contacts left ticked", async () => {
    const sent = answerWith("scam/report-01-created.json");
    renderButton();
    await openSheet();

    await userEvent.clear(textBox());
    await userEvent.type(textBox(), "Pay the fee today or lose the visa slot");
    await userEvent.click(sheet().getByRole("checkbox", { name: /6590000001/ }));
    await userEvent.click(send());

    expect(await screen.findByText(/Other workers can now see your warning/)).toBeTruthy();
    expect(sent).toHaveLength(1);
    expect(sent[0].path).toBe("/api/v2/scam/checks/k_01/report");
    expect(sent[0].json).toEqual({
      indicator_ids: ["f2c46aad"],
      description: "Pay the fee today or lose the visa slot",
    });
  });

  it("can send with every contact unticked", async () => {
    const sent = answerWith("scam/report-01-created.json");
    renderButton();
    await openSheet();

    for (const tick of sheet().getAllByRole("checkbox")) {
      await userEvent.click(tick);
    }
    await userEvent.click(send());

    await screen.findByText(/Other workers can now see your warning/);
    expect(sent[0].json.indicator_ids).toEqual([]);
  });

  it("waits, with the sheet held open, while the report is made", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => (release = resolve));
    answerWith("scam/report-01-created.json", [], gate);
    renderButton();
    await openSheet();

    await userEvent.click(send());

    expect(await sheet().findByRole("button", { name: "Sending…" })).toBeTruthy();
    expect((sheet().getByRole("button", { name: "Sending…" }) as HTMLButtonElement).disabled).toBe(
      true
    );
    // A report in flight is not abandoned by Escape, Cancel or a tap outside.
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("dialog")).toBeTruthy();
    expect((sheet().getByRole("button", { name: "Cancel" }) as HTMLButtonElement).disabled).toBe(
      true
    );

    release();
    expect(await screen.findByText(/Other workers can now see your warning/)).toBeTruthy();
    expect(screen.queryByRole("dialog")).toBeNull();
  });
});

describe("after the warning is sent", () => {
  it("closes the sheet, thanks the worker and links to the Radar page of this kind of scam", async () => {
    answerWith("scam/report-01-created.json");
    renderButton();
    await openSheet();
    await userEvent.click(send());

    expect(await screen.findByText(/Other workers can now see your warning/)).toBeTruthy();

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.getByRole("link", { name: "See it in Radar" }).getAttribute("href")).toBe(
      "/radar/entity/scam-illegal-recruitment-fee"
    );
  });

  it("leaves the button disabled, so the same check cannot be reported twice", async () => {
    answerWith("scam/report-01-created.json");
    renderButton();
    await openSheet();
    await userEvent.click(send());
    await screen.findByText(/Other workers can now see your warning/);

    const done = screen.getByRole("button", { name: "You warned other workers" });
    expect((done as HTMLButtonElement).disabled).toBe(true);
    await userEvent.click(done);

    expect(screen.queryByRole("dialog")).toBeNull();
    expect(screen.queryByRole("button", { name: "Warn other workers" })).toBeNull();
  });

  it("records one scam_reported event, with the kind of scam, for a new warning", async () => {
    answerWith("scam/report-01-created.json");
    renderButton();
    await openSheet();
    expect(trackScamReported).not.toHaveBeenCalled();

    await userEvent.click(send());
    await screen.findByText(/Other workers can now see your warning/);

    expect(trackScamReported).toHaveBeenCalledTimes(1);
    expect(trackScamReported).toHaveBeenCalledWith("illegal_recruitment_fee");
  });

  it("records nothing when the report was refused or the server only had it already", async () => {
    answerWith("scam/report-02-already-reported.json");
    renderButton();
    await openSheet();
    await userEvent.click(send());
    await screen.findByText(/already warned other workers/);

    expect(trackScamReported).not.toHaveBeenCalled();
  });

  it("says so when the server had the report already, and links to it all the same", async () => {
    answerWith("scam/report-02-already-reported.json");
    renderButton();
    await openSheet();
    await userEvent.click(send());

    expect(await screen.findByText(/already warned other workers/)).toBeTruthy();
    expect(screen.getByRole("link", { name: "See it in Radar" }).getAttribute("href")).toBe(
      "/radar/entity/scam-illegal-recruitment-fee"
    );
  });

  it("is already done, and disabled, for a check reported on an earlier day", () => {
    renderButton(scamResult("high", { reported: true, report_id: "r_02" }));

    expect(
      (screen.getByRole("button", { name: "You warned other workers" }) as HTMLButtonElement)
        .disabled
    ).toBe(true);
    expect(screen.getByRole("link", { name: "See it in Radar" }).getAttribute("href")).toBe(
      "/radar/entity/scam-illegal-recruitment-fee"
    );
    expect(screen.queryByRole("status")).toBeNull();
  });
});

describe("when the report fails", () => {
  it("explains a refused message and does not offer to send it again", async () => {
    answerWith("scam/report-error-not-a-scam.json");
    renderButton();
    await openSheet();
    await userEvent.click(send());

    expect((await sheet().findByRole("alert")).textContent).toMatch(
      /looks like a scam can be reported/
    );
    expect((send() as HTMLButtonElement).disabled).toBe(true);
  });

  it("asks the worker to check the text after a validation error, and keeps what they typed", async () => {
    answerWith("scam/report-error-validation.json");
    renderButton();
    await openSheet();
    await userEvent.type(textBox(), " and some more words");
    await userEvent.click(send());

    expect((await sheet().findByRole("alert")).textContent).toMatch(/cannot be sent/);
    expect((textBox() as HTMLTextAreaElement).value).toMatch(/and some more words$/);
    expect((send() as HTMLButtonElement).disabled).toBe(false);
  });

  it("lets the worker try again after a server error, and the second try can work", async () => {
    let calls = 0;
    server.use(
      http.post("*/api/v2/scam/checks/:id/report", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json({ code: "internal_error", message: "x" }, { status: 500 })
          : HttpResponse.json(jsonMocks.get("scam/report-01-created.json")?.body as JsonBodyType, {
              status: 201,
            });
      })
    );
    renderButton();
    await openSheet();
    await userEvent.click(send());
    expect(await sheet().findByRole("alert")).toBeTruthy();

    await userEvent.click(send());

    expect(await screen.findByText(/Other workers can now see your warning/)).toBeTruthy();
    expect(calls).toBe(2);
  });

  it("clears the error when the sheet is closed and opened again", async () => {
    answerWith("scam/report-error-validation.json");
    renderButton();
    await openSheet();
    await userEvent.click(send());
    await sheet().findByRole("alert");

    await userEvent.click(sheet().getByRole("button", { name: "Cancel" }));
    await openSheet();

    expect(sheet().queryByRole("alert")).toBeNull();
  });
});

describe("for a keyboard and a screen reader (NF-SA-019)", () => {
  it("puts focus on the confirmation once the warning is sent, because the button that opened the sheet is gone", async () => {
    answerWith("scam/report-01-created.json");
    renderButton();
    await openSheet();

    await userEvent.click(send());

    const thanks = await screen.findByText(/Other workers can now see your warning/);
    expect(document.activeElement).toBe(thanks);
  });

  it("tabs through the sheet in the order it is drawn: Cancel, then Send", async () => {
    renderButton();
    await openSheet();

    const cancel = sheet().getByRole("button", { name: "Cancel" });
    const sendButton = sheet().getByRole("button", { name: "Send warning" });

    // Next in the tab order, and next down the screen: nothing reorders them on a phone.
    expect(
      cancel.compareDocumentPosition(sendButton) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(dialog().innerHTML).not.toMatch(/reverse/);
  });

  it("keeps the buttons of the sheet at 44 px", async () => {
    renderButton();
    await openSheet();

    for (const name of ["Cancel", "Send warning", "Close"]) {
      expect(sheet().getByRole("button", { name }).className, name).toMatch(/min-h-11|h-11/);
    }
  });
});
