import { http, HttpResponse, type HttpHandler } from "msw";

import { jsonMocks, sseMocks, type MockFile } from "@/mocks/files";

const METHODS = ["GET", "POST", "PUT", "PATCH", "DELETE"] as const;
type Method = (typeof METHODS)[number];

interface RequestLine {
  method: Method;
  /** The path with no query string: a handler matches the path, and the test checks the query. */
  path: string;
}

/** `"GET /api/v2/items?limit=3"` becomes `{ method: "GET", path: "/api/v2/items" }`. */
export function parseRequestLine(line: string): RequestLine {
  const [method, target, ...rest] = line.trim().split(/\s+/);
  if (!METHODS.includes(method as Method) || !target?.startsWith("/") || rest.length > 0) {
    throw new Error(`Not a request line: "${line}". Expected "GET /api/v2/path".`);
  }
  return { method: method as Method, path: target.split("?")[0] };
}

function resolverFor(name: string, mock: MockFile) {
  const status = mock.status;
  if (status === undefined) {
    throw new Error(`Mock "${name}" has no "status", so it is not a single response.`);
  }
  return () =>
    mock.body === undefined
      ? new HttpResponse(null, { status, headers: mock.headers })
      : HttpResponse.json(mock.body, { status, headers: mock.headers });
}

function register({ method, path }: RequestLine, resolver: () => Response): HttpHandler {
  // `*` before the path: a test, a deployed site and a local backend all differ in origin only.
  return http[method.toLowerCase() as Lowercase<Method>](`*${path}`, resolver);
}

/**
 * One handler for one mock file, to use as `server.use(handlerForMock("flags/flags-coach-on.json"))`.
 *
 * @param name Path under `docs/mocks/`, with the extension.
 * @param requestLine Overrides the file's own `request`, which a mock such as an error envelope
 *   does not have because it fits any route.
 */
export function handlerForMock(name: string, requestLine?: string): HttpHandler {
  const mock = jsonMocks.get(name);
  if (mock === undefined) {
    throw new Error(`No mock "${name}" in docs/mocks/. Known: ${[...jsonMocks.keys()].join(", ")}`);
  }
  const line = requestLine ?? mock.request;
  if (line === undefined) {
    throw new Error(
      `Mock "${name}" has no "request"; pass the request line as the second argument.`
    );
  }
  return register(parseRequestLine(line), resolverFor(name, mock));
}

/** A streamed reply: the bytes of a `.sse` mock, as `text/event-stream`. */
export function sseHandler(requestLine: string, name: string): HttpHandler {
  const bytes = sseMocks.get(name);
  if (bytes === undefined) {
    throw new Error(
      `No stream "${name}" in docs/mocks/. Known: ${[...sseMocks.keys()].join(", ")}`
    );
  }
  return register(
    parseRequestLine(requestLine),
    () =>
      new HttpResponse(bytes, {
        status: 200,
        headers: { "Content-Type": "text/event-stream", "Cache-Control": "no-cache" },
      })
  );
}

/**
 * The handlers every test gets: one per distinct `request` that some mock declares. Where several
 * mocks answer the same request (the flags mocks do), the first by name wins, so a test that
 * wants another one swaps it in with `server.use(handlerForMock(...))`.
 */
export function buildDefaultHandlers(): HttpHandler[] {
  const seen = new Set<string>();
  const handlers: HttpHandler[] = [];
  for (const [name, mock] of jsonMocks) {
    if (mock.request === undefined) {
      continue;
    }
    const { method, path } = parseRequestLine(mock.request);
    if (!seen.has(`${method} ${path}`)) {
      seen.add(`${method} ${path}`);
      handlers.push(handlerForMock(name));
    }
  }
  return handlers;
}
