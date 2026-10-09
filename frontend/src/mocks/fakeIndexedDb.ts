// A just-enough IndexedDB for tests of the Coach's offline queue (NF-FC-019): jsdom has none, and
// `fake-indexeddb` would be a new dependency. It does what the queue uses (open with an upgrade, an
// object store with a key path, get, getAll, put, delete, clear) and one thing that matters: a
// transaction runs alone, so a read followed by a write in one transaction cannot be interleaved
// with another one, as in a real browser. Only tests import this module; the app never does.

type Callback = (() => void) | null;

interface FakeRequest<T> {
  result: T;
  error: Error | null;
  onsuccess: Callback;
  onerror: Callback;
  onupgradeneeded?: Callback;
}

type Rows = Map<unknown, unknown>;

const copy = <T>(value: T): T =>
  value === undefined ? value : (JSON.parse(JSON.stringify(value)) as T);

function request<T>(): FakeRequest<T> {
  return { result: undefined as T, error: null, onsuccess: null, onerror: null };
}

export function createFakeIndexedDb(): IDBFactory {
  const databases = new Map<string, Map<string, { keyPath: string; rows: Rows }>>();
  // Every transaction waits for the one before it to finish.
  let turn: Promise<void> = Promise.resolve();

  function database(name: string, stores: Map<string, { keyPath: string; rows: Rows }>) {
    return {
      objectStoreNames: { contains: (store: string) => stores.has(store) },
      createObjectStore(store: string, options: { keyPath: string }) {
        stores.set(store, { keyPath: options.keyPath, rows: new Map() });
      },
      close() {},
      onversionchange: null as Callback,
      transaction(store: string) {
        const found = stores.get(store);
        if (found === undefined) {
          throw new Error(`No store "${store}" in "${name}".`);
        }
        const before = turn;
        let release!: () => void;
        turn = new Promise<void>((resolve) => (release = resolve));
        let pending = 0;
        const run = <R>(work: () => R): FakeRequest<R> => {
          const req = request<R>();
          pending += 1;
          void before
            .then(() => Promise.resolve())
            .then(() => {
              req.result = work();
              req.onsuccess?.();
              pending -= 1;
              if (pending === 0) {
                queueMicrotask(() => {
                  tx.oncomplete?.();
                  release();
                });
              }
            });
          return req;
        };
        const tx = {
          oncomplete: null as Callback,
          onerror: null as Callback,
          onabort: null as Callback,
          error: null,
          objectStore: () => ({
            get: (key: unknown) => run(() => copy(found.rows.get(key))),
            getAll: () => run(() => [...found.rows.values()].map(copy)),
            put: (value: Record<string, unknown>) =>
              run(() => void found.rows.set(value[found.keyPath], copy(value))),
            delete: (key: unknown) => run(() => void found.rows.delete(key)),
            clear: () => run(() => found.rows.clear()),
          }),
        };
        return tx;
      },
    };
  }

  return {
    open(name: string) {
      const req = request<ReturnType<typeof database>>();
      queueMicrotask(() => {
        const existing = databases.get(name);
        const stores = existing ?? new Map();
        databases.set(name, stores);
        req.result = database(name, stores);
        if (existing === undefined) {
          req.onupgradeneeded?.();
        }
        req.onsuccess?.();
      });
      return req as unknown as IDBOpenDBRequest;
    },
    deleteDatabase(name: string) {
      const req = request<undefined>();
      queueMicrotask(() => {
        databases.delete(name);
        req.onsuccess?.();
      });
      return req as unknown as IDBOpenDBRequest;
    },
  } as unknown as IDBFactory;
}
