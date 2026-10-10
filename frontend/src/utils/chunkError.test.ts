import { describe, expect, it } from "vitest";

import { isChunkLoadError } from "@/utils/chunkError";

describe("isChunkLoadError", () => {
  it.each([
    "Failed to fetch dynamically imported module: https://x.web.app/assets/ContractUpload-abc.js",
    "Importing a module script failed.",
    "error loading dynamically imported module",
    "Unable to preload CSS for /assets/index-abc.css",
    "Loading chunk 12 failed.",
  ])("knows %s", (message) => {
    expect(isChunkLoadError(new TypeError(message))).toBe(true);
  });

  it("knows a ChunkLoadError by its name", () => {
    const error = new Error("timeout");
    error.name = "ChunkLoadError";
    expect(isChunkLoadError(error)).toBe(true);
  });

  it("does not mistake a page's own crash for one", () => {
    expect(isChunkLoadError(new TypeError("Cannot read properties of undefined"))).toBe(false);
    expect(isChunkLoadError("boom")).toBe(false);
    expect(isChunkLoadError(null)).toBe(false);
  });
});
