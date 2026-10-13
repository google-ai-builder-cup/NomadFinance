/**
 * A signal that aborts after `ms`, with a `TimeoutError` reason like `AbortSignal.timeout`.
 * `AbortSignal.timeout` is missing from Safari before 16 (iPhone 7 and older stop at iOS 15),
 * Firefox before 100 and Chrome before 103, and a call to it there throws before any request:
 * the Scam Analyzer would not start on those phones.
 */
export function timeoutSignal(ms: number): AbortSignal {
  if (typeof AbortSignal.timeout === "function") {
    return AbortSignal.timeout(ms);
  }
  const controller = new AbortController();
  setTimeout(() => {
    controller.abort(new DOMException("The operation timed out.", "TimeoutError"));
  }, ms);
  return controller.signal;
}
