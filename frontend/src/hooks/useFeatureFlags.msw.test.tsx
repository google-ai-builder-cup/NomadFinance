// @vitest-environment jsdom
// The sample of a frontend test with a mocked network (NF-F0-014): the real hook, the real
// service and the real API client run, and only the backend's answer comes from docs/mocks/.
// The older useFeatureFlag.test.tsx mocks the service instead, which is the right tool for
// logic; use this style when the wiring from the request to the screen is what matters.
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { http, HttpResponse } from "msw";
import type { ReactNode } from "react";
import { describe, expect, it, vi } from "vitest";

import { useFeatureFlags } from "@/hooks/useFeatureFlag";
import { handlerForMock } from "@/mocks/handlers";
import { server, setupMockServer } from "@/mocks/server";

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => ({ user: { uid: "alice" }, loading: false }) }));
vi.mock("@/services/authService", () => ({ getIdToken: async () => "test-token" }));

setupMockServer();

function renderFlags() {
  // No retries: a failing answer should show at once, not after the default three attempts.
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
  return renderHook(() => useFeatureFlags(), { wrapper });
}

describe("useFeatureFlags against the mock API", () => {
  it("is everything off while waiting, then what the default mock says", async () => {
    const { result } = renderFlags();

    expect(result.current).toEqual({ flags: { coach: false, scam: false }, isLoading: true });
    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.flags).toEqual({ coach: false, scam: false });
  });

  it("turns the Coach on when the backend says so", async () => {
    server.use(handlerForMock("flags/flags-coach-on.json"));

    const { result } = renderFlags();

    await waitFor(() => expect(result.current.flags.coach).toBe(true));
    expect(result.current.flags.scam).toBe(false);
  });

  it("sends the signed-in worker's token", async () => {
    let authorization: string | null = null;
    server.use(
      http.get("*/api/v2/flags", ({ request }) => {
        authorization = request.headers.get("Authorization");
        return HttpResponse.json({ coach: false, scam: true });
      })
    );

    const { result } = renderFlags();

    await waitFor(() => expect(result.current.flags.scam).toBe(true));
    expect(authorization).toBe("Bearer test-token");
  });

  it("stays everything off when the backend refuses with the error envelope", async () => {
    server.use(handlerForMock("flags/flags-unauthenticated.json"));

    const { result } = renderFlags();

    await waitFor(() => expect(result.current.isLoading).toBe(false));
    expect(result.current.flags).toEqual({ coach: false, scam: false });
  });
});
