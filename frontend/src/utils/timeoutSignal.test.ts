import { afterEach, describe, expect, it, vi } from "vitest";

import { timeoutSignal } from "@/utils/timeoutSignal";

afterEach(() => {
  vi.useRealTimers();
  vi.unstubAllGlobals();
});

describe("timeoutSignal", () => {
  it("uses the browser's own when it has one", () => {
    const own = new AbortController().signal;
    const timeout = vi.fn(() => own);
    vi.stubGlobal("AbortSignal", { timeout });

    expect(timeoutSignal(5000)).toBe(own);
    expect(timeout).toHaveBeenCalledWith(5000);
  });

  it("works where AbortSignal.timeout does not exist (Safari before 16)", () => {
    vi.useFakeTimers();
    vi.stubGlobal("AbortSignal", class {});

    const signal = timeoutSignal(5000);
    expect(signal.aborted).toBe(false);
    vi.advanceTimersByTime(4999);
    expect(signal.aborted).toBe(false);
    vi.advanceTimersByTime(1);

    expect(signal.aborted).toBe(true);
    expect((signal.reason as DOMException).name).toBe("TimeoutError");
  });
});
