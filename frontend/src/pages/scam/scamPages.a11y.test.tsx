// @vitest-environment jsdom
// Accessibility and translation of the scam module's pages (NF-SA-019): the check screen in each
// of its states, the history and a stored check, run against the mock API in all six languages,
// checked with axe and for any string that would show as a raw key. The parts they are made of
// are in src/components/scam/scamParts.a11y.test.tsx.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type JsonBodyType } from "msw";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeAll, describe, expect, it, vi } from "vitest";

import { loadNamespace, setLanguage } from "@/lib/i18n";
import { axeViolations, rawKeysShown } from "@/mocks/axe";
import { jsonMocks } from "@/mocks/files";
import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";
import ScamCheckDetail from "@/pages/scam/ScamCheckDetail";
import ScamCheckHome from "@/pages/scam/ScamCheckHome";
import ScamHistory from "@/pages/scam/ScamHistory";
import { LANGUAGE_CODES } from "@/types/enums";

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "alice" }, loading: false }) }));
vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));
vi.mock("@/hooks/useUser", () => ({
  useUserProfile: () => ({ data: { host_country: "SG", home_country: "IN" } }),
}));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("scam");
});

afterEach(async () => {
  cleanup();
  sessionStorage.clear();
  await act(() => setLanguage("en"));
});

function renderAt(entry: string) {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <main>
          <Routes>
            <Route path="/scam-check" element={<ScamCheckHome />} />
            <Route path="/scam-check/history" element={<ScamHistory />} />
            <Route path="/scam-check/history/:id" element={<ScamCheckDetail />} />
          </Routes>
        </main>
      </MemoryRouter>
    </QueryClientProvider>
  );
}

async function expectFit(container: HTMLElement) {
  expect(await axeViolations(container)).toEqual([]);
  expect(rawKeysShown(container)).toEqual([]);
}

const inLanguage = (code: string) => act(() => setLanguage(code));

describe.each(LANGUAGE_CODES)("in %s", (language) => {
  it("the check screen, ready for a message", async () => {
    await inLanguage(language);
    const { container } = renderAt("/scam-check");

    await expectFit(container);
  });

  it("the check screen, with a message shared into it", async () => {
    await inLanguage(language);
    const { container } = renderAt("/scam-check?text=Pay%20800%20SGD%20now");

    await expectFit(container);
  });

  it("the history, with its checks", async () => {
    await inLanguage(language);
    const { container } = renderAt("/scam-check/history");
    await screen.findAllByRole("listitem");

    await expectFit(container);
  });

  it("a stored check", async () => {
    await inLanguage(language);
    const { container } = renderAt("/scam-check/history/k_01");
    await screen.findAllByRole("heading", { level: 2 });

    await expectFit(container);
  });
});

describe("the check screen", () => {
  it("in screenshot mode, with nothing chosen and with a screenshot chosen", async () => {
    const { container } = renderAt("/scam-check");
    await userEvent.click(screen.getByRole("button", { name: "Screenshot" }));
    await expectFit(container);

    const input = container.querySelector('input[type="file"]:not([capture])') as HTMLInputElement;
    await userEvent.upload(input, new File(["x"], "chat.png", { type: "image/png" }));

    expect(await screen.findByRole("button", { name: "Remove screenshot" })).toBeTruthy();
    await expectFit(container);
  });

  it("while it waits for the answer, and after a long wait", async () => {
    let release: () => void = () => undefined;
    const gate = new Promise<void>((resolve) => (release = resolve));
    server.use(
      http.post("*/api/v2/scam/analyze", async () => {
        await gate;
        return HttpResponse.json(
          jsonMocks.get("scam/analyze-01-high-risk.json")?.body as JsonBodyType
        );
      })
    );
    const { container } = renderAt("/scam-check?text=Pay%20800%20SGD%20now");
    await userEvent.click(screen.getByRole("button", { name: "Check this message" }));

    expect(await screen.findByRole("status")).toBeTruthy();
    await expectFit(container);
    release();
  });

  it("with the answer, a scam", async () => {
    const { container } = renderAt("/scam-check?text=Pay%20800%20SGD%20now");
    await userEvent.click(screen.getByRole("button", { name: "Check this message" }));

    expect(
      await screen.findByRole("heading", { level: 2, name: "This looks like a scam" })
    ).toBeTruthy();
    await expectFit(container);
  });

  it.each([
    ["too many checks", "scam/analyze-error-rate-limited.json"],
    ["an unreadable screenshot", "scam/analyze-error-image-unreadable.json"],
    ["a message too long", "scam/analyze-error-text-too-long.json"],
  ])("with the error for %s", async (_name, mock) => {
    server.use(handlerForMock(mock, "POST /api/v2/scam/analyze"));
    const { container } = renderAt("/scam-check?text=Pay%20800%20SGD%20now");
    await userEvent.click(screen.getByRole("button", { name: "Check this message" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    await expectFit(container);
  });
});

describe("the history", () => {
  it("empty", async () => {
    server.use(handlerForMock("scam/checks-list-03-empty.json"));
    const { container } = renderAt("/scam-check/history");

    expect(await screen.findByRole("heading", { level: 2, name: "No checks yet" })).toBeTruthy();
    await expectFit(container);
  });

  it("that could not be loaded", async () => {
    server.use(
      http.get("*/api/v2/scam/checks", () =>
        HttpResponse.json({ code: "internal_error", message: "x" }, { status: 500 })
      )
    );
    const { container } = renderAt("/scam-check/history");

    expect(await screen.findByRole("alert")).toBeTruthy();
    await expectFit(container);
  });
});

describe("a stored check", () => {
  it("that is gone", async () => {
    server.use(handlerForMock("scam/check-error-not-found.json"));
    const { container } = renderAt("/scam-check/history/k_missing");

    expect(
      await screen.findByRole("heading", { level: 2, name: "We could not find this check" })
    ).toBeTruthy();
    await expectFit(container);
  });

  it("that could not be loaded", async () => {
    server.use(
      http.get("*/api/v2/scam/checks/k_01", () =>
        HttpResponse.json({ code: "internal_error", message: "x" }, { status: 500 })
      )
    );
    const { container } = renderAt("/scam-check/history/k_01");

    expect(await screen.findByRole("alert")).toBeTruthy();
    await expectFit(container);
  });

  it("not a scam, and already reported", async () => {
    server.use(handlerForMock("scam/check-04-benign.json"));
    const { container } = renderAt("/scam-check/history/k_04");
    await screen.findAllByRole("heading", { level: 2 });

    await expectFit(container);
  });
});

describe("the check screen after a mistake", () => {
  it("with a message that is too long", async () => {
    const { container } = renderAt("/scam-check");
    fireEvent.change(screen.getByLabelText("The message you received"), {
      target: { value: "Pay the fee now. ".repeat(300) },
    });

    expect((await screen.findAllByRole("alert")).length).toBeGreaterThan(0);
    await expectFit(container);
  });

  it("with a file of a kind that cannot be checked", async () => {
    const user = userEvent.setup({ applyAccept: false });
    const { container } = renderAt("/scam-check");
    await user.click(screen.getByRole("button", { name: "Screenshot" }));

    const input = container.querySelector('input[type="file"]:not([capture])') as HTMLInputElement;
    await user.upload(input, new File(["x"], "chat.gif", { type: "image/gif" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    await expectFit(container);
  });
});

describe("the history when more could not be loaded", () => {
  it("keeps its rows and says so", async () => {
    let calls = 0;
    server.use(
      http.get("*/api/v2/scam/checks", () => {
        calls += 1;
        return calls === 1
          ? HttpResponse.json(
              jsonMocks.get("scam/checks-list-01-first-page.json")?.body as JsonBodyType
            )
          : HttpResponse.json({ code: "internal_error", message: "x" }, { status: 500 });
      })
    );
    const { container } = renderAt("/scam-check/history");
    await screen.findAllByRole("listitem");
    await userEvent.click(screen.getByRole("button", { name: "Show more" }));

    expect(await screen.findByRole("alert")).toBeTruthy();
    await expectFit(container);
  });
});
