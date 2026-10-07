// @vitest-environment jsdom
// The check screen against the mock API (NF-SA-015): the real page, hook, service and API client
// run, and only the backend's answers come from docs/mocks/scam/. Paste, upload and share must
// all leave through the same request.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { http, HttpResponse, type JsonBodyType } from "msw";
import { MemoryRouter, useLocation } from "react-router-dom";
import { afterEach, beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

import { jsonMocks } from "@/mocks/files";
import { server, setupMockServer } from "@/mocks/server";
import { loadNamespace } from "@/lib/i18n";
import ScamCheckHome from "@/pages/scam/ScamCheckHome";
import { MAX_MESSAGE_CHARS, stashSharedMessage } from "@/utils/scamInput";

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "alice" }, loading: false }) }));
vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));
vi.mock("@/hooks/useUser", () => ({
  useUserProfile: () => ({ data: { host_country: "SG", home_country: "IN" } }),
}));

setupMockServer();

beforeAll(async () => {
  await loadNamespace("scam");
});

interface Sent {
  contentType: string;
  json?: Record<string, unknown>;
  form?: FormData;
}

/** Answers the analyze route with a mock file and records what the page sent. */
function answerWith(mockName: string, sent: Sent[] = []): Sent[] {
  const mock = jsonMocks.get(mockName);
  if (mock?.status === undefined) {
    throw new Error(`No single-response mock ${mockName}`);
  }
  server.use(
    http.post("*/api/v2/scam/analyze", async ({ request }) => {
      const contentType = request.headers.get("Content-Type") ?? "";
      sent.push(
        contentType.startsWith("multipart/form-data")
          ? { contentType, form: await request.formData() }
          : { contentType, json: (await request.json()) as Record<string, unknown> }
      );
      return HttpResponse.json(mock.body as JsonBodyType, {
        status: mock.status,
        headers: mock.headers,
      });
    })
  );
  return sent;
}

function LocationProbe() {
  const location = useLocation();
  return <output data-testid="location">{location.pathname + location.search}</output>;
}

function renderPage(entry = "/scam-check") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={client}>
      <MemoryRouter initialEntries={[entry]}>
        <ScamCheckHome />
        <LocationProbe />
      </MemoryRouter>
    </QueryClientProvider>
  );
}

const submitButton = () => screen.getByRole("button", { name: "Check this message" });
const messageBox = () => screen.getByLabelText("The message you received");
const png = () => new File(["fake image"], "chat.png", { type: "image/png" });

beforeEach(() => sessionStorage.clear());
afterEach(cleanup);

describe("pasting a message", () => {
  it("sends it as JSON with the worker's language and route, then shows the answer", async () => {
    const sent = answerWith("scam/analyze-01-high-risk.json");
    const user = userEvent.setup();
    renderPage();

    await user.type(messageBox(), "  Pay 800 SGD today  ");
    await user.click(submitButton());

    expect(await screen.findByText("This looks like a scam")).toBeTruthy();
    expect(screen.getByText("High risk")).toBeTruthy();
    expect(sent).toHaveLength(1);
    expect(sent[0].contentType).toContain("application/json");
    expect(sent[0].json).toEqual({
      text: "Pay 800 SGD today",
      language: "en",
      corridor_id: "SG-IN",
    });
  });

  it("shows the reassurance for a message that is not a scam", async () => {
    answerWith("scam/analyze-04-benign.json");
    const user = userEvent.setup();
    renderPage();

    await user.type(messageBox(), "Your parcel arrives tomorrow");
    await user.click(submitButton());

    expect(await screen.findByText("This does not look like a scam")).toBeTruthy();
    expect(screen.getByText("No scam found")).toBeTruthy();
  });

  it("offers a new check after an answer", async () => {
    answerWith("scam/analyze-04-benign.json");
    const user = userEvent.setup();
    renderPage();
    await user.type(messageBox(), "hello");
    await user.click(submitButton());

    await user.click(await screen.findByRole("button", { name: "Check another message" }));

    expect((messageBox() as HTMLTextAreaElement).value).toBe("");
  });

  it("keeps the submit button off while there is nothing to check", async () => {
    const user = userEvent.setup();
    renderPage();
    expect((submitButton() as HTMLButtonElement).disabled).toBe(true);

    await user.type(messageBox(), "   ");
    expect((submitButton() as HTMLButtonElement).disabled).toBe(true);
  });

  it("counts characters and refuses a message over the limit without cutting it", async () => {
    const sent = answerWith("scam/analyze-01-high-risk.json");
    const user = userEvent.setup();
    renderPage();

    await user.click(messageBox());
    await user.paste("a".repeat(MAX_MESSAGE_CHARS + 1));

    expect(screen.getByText(`${MAX_MESSAGE_CHARS + 1} / ${MAX_MESSAGE_CHARS}`)).toBeTruthy();
    expect(screen.getByRole("alert").textContent).toContain("too long");
    expect((submitButton() as HTMLButtonElement).disabled).toBe(true);
    expect((messageBox() as HTMLTextAreaElement).value).toHaveLength(MAX_MESSAGE_CHARS + 1);
    expect(sent).toHaveLength(0);
  });
});

describe("uploading a screenshot", () => {
  it("sends it as a form to the same route", async () => {
    const sent = answerWith("scam/analyze-01-high-risk.json");
    const user = userEvent.setup();
    renderPage();

    await user.click(screen.getByRole("button", { name: "Screenshot" }));
    await user.upload(screen.getByLabelText("Choose a screenshot"), png());
    expect(await screen.findByText("chat.png")).toBeTruthy();
    await user.click(submitButton());

    expect(await screen.findByText("This looks like a scam")).toBeTruthy();
    expect(sent).toHaveLength(1);
    expect(sent[0].contentType).toContain("multipart/form-data");
    expect(sent[0].form?.get("language")).toBe("en");
    expect(sent[0].form?.get("corridor_id")).toBe("SG-IN");
    // jsdom's File does not keep its name through Node's fetch (a browser does), so the
    // content and type are what is checked here.
    const image = sent[0].form?.get("image") as File;
    expect(image.type).toBe("image/png");
    expect(await image.text()).toBe("fake image");
  });

  it("does not send the typed text while the screenshot mode has no picture", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.type(messageBox(), "some text");

    await user.click(screen.getByRole("button", { name: "Screenshot" }));

    expect((submitButton() as HTMLButtonElement).disabled).toBe(true);
  });

  it("lets the worker remove the picture and choose another", async () => {
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Screenshot" }));
    await user.upload(screen.getByLabelText("Choose a screenshot"), png());

    await user.click(await screen.findByRole("button", { name: "Remove screenshot" }));

    expect(screen.getByLabelText("Choose a screenshot")).toBeTruthy();
  });

  it("refuses a camera photo of a type the backend would refuse", async () => {
    const user = userEvent.setup({ applyAccept: false });
    const { container } = renderPage();
    await user.click(screen.getByRole("button", { name: "Screenshot" }));

    const camera = container.querySelector("input[capture]") as HTMLInputElement;
    await user.upload(camera, new File(["x"], "scan.heic", { type: "image/heic" }));

    expect((await screen.findByRole("alert")).textContent).toContain("JPEG, PNG or WebP");
  });
});

describe("sharing a message into the app", () => {
  it("fills the box, cleans the address and sends nothing until the worker taps Check", async () => {
    const sent = answerWith("scam/analyze-01-high-risk.json");
    const user = userEvent.setup();
    renderPage("/scam-check?title=&text=Pay%20800%20SGD%20now&url=");

    expect((messageBox() as HTMLTextAreaElement).value).toBe("Pay 800 SGD now");
    expect(screen.getByText(/We added the message you shared/)).toBeTruthy();
    await waitFor(() => expect(screen.getByTestId("location").textContent).toBe("/scam-check"));
    expect(sent).toHaveLength(0);

    await user.click(submitButton());

    expect(await screen.findByText("This looks like a scam")).toBeTruthy();
    expect(sent[0].json).toEqual({ text: "Pay 800 SGD now", language: "en", corridor_id: "SG-IN" });
  });

  it("finds a message shared before the worker signed in, once", () => {
    stashSharedMessage("?text=Fee%20due%20today");
    const first = renderPage();

    expect((messageBox() as HTMLTextAreaElement).value).toBe("Fee due today");
    expect(sessionStorage.length).toBe(0);

    first.unmount();
    renderPage();
    expect((messageBox() as HTMLTextAreaElement).value).toBe("");
  });
});

describe("when the check fails", () => {
  async function submitText(user: ReturnType<typeof userEvent.setup>) {
    await user.type(messageBox(), "hello");
    await user.click(submitButton());
  }

  it("tells a worker over the hourly limit how long to wait, with no retry button", async () => {
    answerWith("scam/analyze-error-rate-limited.json");
    const user = userEvent.setup();
    renderPage();

    await submitText(user);

    expect((await screen.findByRole("alert")).textContent).toContain("Try again in about 23 min");
    expect(screen.queryByRole("button", { name: "Try again" })).toBeNull();
    expect((messageBox() as HTMLTextAreaElement).value).toBe("hello");
  });

  it("explains an unreadable screenshot", async () => {
    answerWith("scam/analyze-error-image-unreadable.json");
    const user = userEvent.setup();
    renderPage();
    await user.click(screen.getByRole("button", { name: "Screenshot" }));
    await user.upload(screen.getByLabelText("Choose a screenshot"), png());

    await user.click(submitButton());

    expect((await screen.findByRole("alert")).textContent).toContain("could not read any message");
  });

  it("offers Try again for a busy checker and repeats the same request", async () => {
    server.use(
      http.post("*/api/v2/scam/analyze", () =>
        HttpResponse.json({ code: "ai_busy", message: "busy", request_id: "r" }, { status: 503 })
      )
    );
    const user = userEvent.setup();
    renderPage();
    await submitText(user);

    const retry = await screen.findByRole("button", { name: "Try again" });
    const sent = answerWith("scam/analyze-04-benign.json");
    await user.click(retry);

    expect(await screen.findByText("This does not look like a scam")).toBeTruthy();
    expect(sent[0].json?.text).toBe("hello");
  });

  it("shows that the explanation is missing when the verdict came without it", async () => {
    answerWith("scam/analyze-06-explainer-unavailable.json");
    const user = userEvent.setup();
    renderPage();

    await submitText(user);

    expect(await screen.findByText("This looks like a scam")).toBeTruthy();
    expect(screen.getByText(/could not write the full explanation/)).toBeTruthy();
  });
});
