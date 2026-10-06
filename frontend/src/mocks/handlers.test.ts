import { describe, expect, it } from "vitest";

import { jsonMocks, sseMocks } from "@/mocks/files";
import {
  buildDefaultHandlers,
  handlerForMock,
  parseRequestLine,
  sseHandler,
} from "@/mocks/handlers";

describe("parseRequestLine", () => {
  it("reads the method and the path", () => {
    expect(parseRequestLine("GET /api/v2/flags")).toEqual({ method: "GET", path: "/api/v2/flags" });
    expect(parseRequestLine("  POST   /api/v2/scam/analyze ")).toEqual({
      method: "POST",
      path: "/api/v2/scam/analyze",
    });
  });

  it("drops the query string, which a handler cannot match on", () => {
    expect(parseRequestLine("GET /api/v2/example/items?limit=3&cursor=abc").path).toBe(
      "/api/v2/example/items"
    );
  });

  it.each(["", "/api/v2/flags", "FETCH /api/v2/flags", "GET api/v2/flags", "GET /a /b"])(
    "refuses %j, naming what it expected",
    (line) => {
      expect(() => parseRequestLine(line)).toThrow(/Expected "GET \/api\/v2\/path"/);
    }
  );
});

describe("the mocks of docs/mocks/", () => {
  it("are found, with their path under docs/mocks/ as the name", () => {
    expect(jsonMocks.has("flags/flags-all-off.json")).toBe(true);
    expect(jsonMocks.has("conventions/error-not-found.json")).toBe(true);
    expect(sseMocks.has("conventions/sse-stream-done.sse")).toBe(true);
  });

  it("every one that declares a request also has a status", () => {
    for (const [name, mock] of jsonMocks) {
      if (mock.request !== undefined) {
        expect(typeof mock.status, name).toBe("number");
      }
    }
  });

  it("every request line that a mock declares can be parsed", () => {
    for (const { request } of jsonMocks.values()) {
      if (request !== undefined) {
        expect(() => parseRequestLine(request)).not.toThrow();
      }
    }
  });
});

describe("handlers", () => {
  it("make one default handler per distinct request, however many mocks share it", () => {
    const requests = new Set(
      [...jsonMocks.values()]
        .flatMap((mock) => (mock.request === undefined ? [] : [parseRequestLine(mock.request)]))
        .map(({ method, path }) => `${method} ${path}`)
    );

    expect(buildDefaultHandlers()).toHaveLength(requests.size);
  });

  it("name the known mocks when asked for one that does not exist", () => {
    expect(() => handlerForMock("flags/nope.json")).toThrow(/Known: .*flags\/flags-all-off\.json/);
    expect(() => sseHandler("POST /api/v2/x", "nope.sse")).toThrow(/Known: /);
  });

  it("need a request line from a mock that has none", () => {
    expect(() => handlerForMock("conventions/error-not-found.json")).toThrow(/no "request"/);
    expect(() =>
      handlerForMock("conventions/error-not-found.json", "GET /api/v2/anything")
    ).not.toThrow();
  });
});
