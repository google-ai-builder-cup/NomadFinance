import { setupServer } from "msw/node";
import { afterAll, afterEach, beforeAll } from "vitest";

import { buildDefaultHandlers } from "@/mocks/handlers";

/** The mock API of a test file. Import it to swap a handler: `server.use(handlerForMock(...))`. */
export const server = setupServer(...buildDefaultHandlers());

/**
 * Call once at the top of a test file that talks to the network through `fetch`. It is opt-in, so
 * tests that mock their own services are not affected. A request nobody mocked fails the test,
 * instead of reaching a real address.
 */
export function setupMockServer(): void {
  beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());
}
