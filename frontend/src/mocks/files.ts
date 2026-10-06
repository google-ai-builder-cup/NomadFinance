// The mock files of docs/mocks/ as the frontend tests see them. They are read from disk, so there
// is no copy: a change to a mock reaches the tests on their next run. Node's file system rather
// than Vite's `import.meta.glob`, because the folder is outside the frontend and Vite refuses
// some imports from outside its root when a test runs in the jsdom environment.
// Only tests import this module; the app never does.
import { readdirSync, readFileSync } from "node:fs";
import path from "node:path";

export interface MockFile {
  /** What the mock is for, in a sentence. Not used by code. */
  description?: string;
  /** `"GET /api/v2/flags"`. A mock without one is used by name, for a request a test chooses. */
  request?: string;
  /** Absent in a mock that scripts a whole exchange of steps (`idempotency-exchange.json`). */
  status?: number;
  headers?: Record<string, string>;
  body?: unknown;
}

// `pnpm test` runs from frontend/. `import.meta.url` is not a file address in the jsdom environment.
const MOCKS_DIR = path.resolve(process.cwd(), "../docs/mocks") + "/";

/** Every file under `docs/mocks/` with this extension, by its path inside that folder, in name order. */
function readMocks<T>(extension: string, parse: (text: string) => T): ReadonlyMap<string, T> {
  const names = (readdirSync(MOCKS_DIR, { recursive: true }) as string[])
    .map((name) => name.replaceAll("\\", "/"))
    .filter((name) => name.endsWith(extension))
    .sort((a, b) => a.localeCompare(b));
  return new Map(names.map((name) => [name, parse(readFileSync(MOCKS_DIR + name, "utf8"))]));
}

/** Every JSON mock, by its path under `docs/mocks/` (with the extension), in name order. */
export const jsonMocks: ReadonlyMap<string, MockFile> = readMocks(
  ".json",
  (text) => JSON.parse(text) as MockFile
);

/** Every `.sse` mock: the raw bytes of a streamed response. */
export const sseMocks: ReadonlyMap<string, string> = readMocks(".sse", (text) => text);
