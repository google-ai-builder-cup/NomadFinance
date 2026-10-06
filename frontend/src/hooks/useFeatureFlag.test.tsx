import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderToStaticMarkup } from "react-dom/server";
import { beforeEach, describe, expect, it, vi } from "vitest";

import { useFeatureFlag, useFeatureFlags } from "@/hooks/useFeatureFlag";
import { getFeatureFlags } from "@/services/featureFlagService";

const auth = vi.hoisted(() => ({ user: null as { uid: string } | null, loading: false }));

vi.mock("@/hooks/useAuth", () => ({ useAuth: () => auth }));
vi.mock("@/services/featureFlagService", () => ({ getFeatureFlags: vi.fn() }));

function Probe() {
  const { flags, isLoading } = useFeatureFlags();
  const coach = useFeatureFlag("coach");
  return <span data-state={JSON.stringify({ flags, isLoading, coach })} />;
}

function render(client: QueryClient): { flags: unknown; isLoading: boolean; coach: unknown } {
  const markup = renderToStaticMarkup(
    <QueryClientProvider client={client}>
      <Probe />
    </QueryClientProvider>
  );
  const state = /data-state="([^"]*)"/.exec(markup)?.[1] ?? "";
  return JSON.parse(state.replaceAll("&quot;", '"')) as ReturnType<typeof render>;
}

beforeEach(() => {
  auth.user = null;
  vi.mocked(getFeatureFlags).mockReset();
});

describe("useFeatureFlags", () => {
  it("is everything off, and not waiting, while nobody is signed in", () => {
    const state = render(new QueryClient());

    expect(state.flags).toEqual({ coach: false, scam: false });
    expect(state.isLoading).toBe(false);
    expect(vi.mocked(getFeatureFlags)).not.toHaveBeenCalled();
  });

  it("is everything off, and waiting, until the first answer arrives", () => {
    auth.user = { uid: "alice" };
    vi.mocked(getFeatureFlags).mockReturnValue(new Promise(() => undefined));

    const state = render(new QueryClient());

    expect(state.flags).toEqual({ coach: false, scam: false });
    expect(state.isLoading).toBe(true);
    expect(state.coach).toEqual({ enabled: false, isLoading: true });
  });

  it("reports the modules the backend turned on for this user", () => {
    auth.user = { uid: "alice" };
    const client = new QueryClient();
    client.setQueryData(["featureFlags", "alice"], { coach: true, scam: false });

    const state = render(client);

    expect(state.flags).toEqual({ coach: true, scam: false });
    expect(state.coach).toEqual({ enabled: true, isLoading: false });
  });

  it("never shows one account's answer to the next account that signs in", () => {
    const client = new QueryClient();
    client.setQueryData(["featureFlags", "alice"], { coach: true, scam: true });
    auth.user = { uid: "bob" };
    vi.mocked(getFeatureFlags).mockReturnValue(new Promise(() => undefined));

    const state = render(client);

    expect(state.flags).toEqual({ coach: false, scam: false });
  });
});
