import { onlineManager } from "@tanstack/react-query";
import { afterEach, describe, expect, it } from "vitest";

import { queryClient } from "@/lib/queryClient";
import { ApiError } from "@/services/apiClient";

describe("queryClient while the browser says it is offline", () => {
  afterEach(() => {
    onlineManager.setOnline(true);
    queryClient.clear();
  });

  it("runs a mutation instead of leaving the form waiting", async () => {
    onlineManager.setOnline(false);

    const result = await queryClient
      .getMutationCache()
      .build(queryClient, { mutationFn: async () => "sent" })
      .execute(undefined);

    expect(result).toBe("sent");
  });

  it("fails a query with the app's offline error instead of staying pending", async () => {
    onlineManager.setOnline(false);

    await expect(
      queryClient.fetchQuery({
        queryKey: ["offline-test"],
        queryFn: () => Promise.reject(new ApiError(0, "Network error")),
        retry: false,
      })
    ).rejects.toMatchObject({ status: 0 });
  });
});
