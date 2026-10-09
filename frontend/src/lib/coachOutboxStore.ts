import { type Claimant, type OutboxEntry, isClaimable, withClaim } from "@/utils/coachOutbox";
import {
  OUTBOX_DB_NAME,
  OUTBOX_DB_VERSION,
  OUTBOX_STORE,
  OUTBOX_SYNC_TAG,
} from "@/utils/coachStorageKeys";

// Where the answer that is waiting for a connection is kept (NF-FC-019): IndexedDB, because the
// service worker (public/coach-outbox-sw.js) reads the same database when no page is open.
// Where IndexedDB is missing or refuses (some private windows) the answer is kept in memory, which
// still covers the open tab.

export interface OutboxBackend {
  get(id: string): Promise<OutboxEntry | undefined>;
  put(entry: OutboxEntry): Promise<void>;
  delete(id: string): Promise<void>;
  /** Read, decide and write in one step that no other tab or worker can get in between. */
  update<R>(
    id: string,
    change: (current: OutboxEntry | undefined) => { next?: OutboxEntry; result: R }
  ): Promise<R>;
}

export function memoryBackend(): OutboxBackend {
  const entries = new Map<string, OutboxEntry>();
  return {
    get: async (id) => entries.get(id),
    put: async (entry) => void entries.set(entry.id, entry),
    delete: async (id) => void entries.delete(id),
    update: async (id, change) => {
      const { next, result } = change(entries.get(id));
      if (next) {
        entries.set(id, next);
      }
      return result;
    },
  };
}

export function indexedDbBackend(): OutboxBackend {
  let opened: Promise<IDBDatabase> | null = null;
  const open = (): Promise<IDBDatabase> => {
    opened ??= new Promise((resolve, reject) => {
      const request = indexedDB.open(OUTBOX_DB_NAME, OUTBOX_DB_VERSION);
      request.onupgradeneeded = () => {
        request.result.createObjectStore(OUTBOX_STORE, { keyPath: "id" });
      };
      request.onsuccess = () => {
        // Signing out deletes the database: let go of it so the deletion is not left waiting.
        request.result.onversionchange = () => {
          request.result.close();
          opened = null;
        };
        resolve(request.result);
      };
      request.onerror = () => {
        opened = null;
        reject(request.error);
      };
    });
    return opened;
  };

  const run = async <R>(
    mode: IDBTransactionMode,
    work: (store: IDBObjectStore, done: (value: R) => void) => void
  ): Promise<R> => {
    const db = await open();
    return new Promise<R>((resolve, reject) => {
      const tx = db.transaction(OUTBOX_STORE, mode);
      let value!: R;
      work(tx.objectStore(OUTBOX_STORE), (found) => {
        value = found;
      });
      tx.oncomplete = () => resolve(value);
      tx.onerror = tx.onabort = () => reject(tx.error);
    });
  };

  return {
    get: (id) =>
      run<OutboxEntry | undefined>("readonly", (store, done) => {
        const request = store.get(id);
        request.onsuccess = () => done(request.result as OutboxEntry | undefined);
      }),
    put: (entry) => run<void>("readwrite", (store) => void store.put(entry)),
    delete: (id) => run<void>("readwrite", (store) => void store.delete(id)),
    update: <R>(
      id: string,
      change: (current: OutboxEntry | undefined) => { next?: OutboxEntry; result: R }
    ) =>
      run<R>("readwrite", (store, done) => {
        const request = store.get(id);
        request.onsuccess = () => {
          const { next, result } = change(request.result as OutboxEntry | undefined);
          if (next) {
            store.put(next);
          }
          done(result);
        };
      }),
  };
}

let backend: OutboxBackend | null = null;

function current(): OutboxBackend {
  backend ??= typeof indexedDB === "undefined" ? memoryBackend() : indexedDbBackend();
  return backend;
}

/** Tests choose the backend; `null` lets the next call pick again. */
export function setOutboxBackend(next: OutboxBackend | null): void {
  backend = next;
}

// A storage failure never reaches the screen: the answer then waits in memory for this tab.
async function call<R>(work: (store: OutboxBackend) => Promise<R>): Promise<R> {
  try {
    return await work(current());
  } catch {
    backend = memoryBackend();
    return work(backend);
  }
}

export const saveEntry = (entry: OutboxEntry): Promise<void> => call((store) => store.put(entry));
export const readEntry = (id: string): Promise<OutboxEntry | undefined> =>
  call((store) => store.get(id));
export const removeEntry = (id: string): Promise<void> => call((store) => store.delete(id));

export type ClaimResult =
  | { status: "claimed"; entry: OutboxEntry }
  /** Someone else is sending it right now. */
  | { status: "busy" }
  /** It is not there: sent by someone else already, or never saved. */
  | { status: "gone" };

/** Take the answer to send it. Only one of the page and the service worker gets it. */
export function claimEntry(id: string, by: Claimant, now = Date.now()): Promise<ClaimResult> {
  return call((store) =>
    store.update<ClaimResult>(id, (entry) => {
      if (entry === undefined) {
        return { result: { status: "gone" } };
      }
      if (!isClaimable(entry, now)) {
        return { result: { status: "busy" } };
      }
      const next = withClaim(entry, by, now);
      return { next, result: { status: "claimed", entry: next } };
    })
  );
}

export function releaseEntry(id: string): Promise<void> {
  return call((store) =>
    store.update<void>(id, (entry) => ({
      next: entry && { ...entry, claim: null },
      result: undefined,
    }))
  );
}

// ---- the service worker ----

const SW_URL = "/coach-outbox-sw.js";
// Its own scope, like the push worker (lib/messaging.ts): the app's own service worker owns "/",
// and this one only has to be woken by Background Sync, never to answer a page's requests.
const SW_SCOPE = "/coach-outbox-scope";

type SyncRegistration = ServiceWorkerRegistration & {
  sync?: { register(tag: string): Promise<void> };
};

function activated(registration: ServiceWorkerRegistration): Promise<void> {
  const worker = registration.installing ?? registration.waiting ?? registration.active;
  if (worker === null || worker.state === "activated") {
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    const check = () => {
      if (worker.state === "activated" || worker.state === "redundant") {
        worker.removeEventListener("statechange", check);
        resolve();
      }
    };
    worker.addEventListener("statechange", check);
  });
}

async function registration(): Promise<SyncRegistration | null> {
  if (typeof navigator === "undefined" || !("serviceWorker" in navigator)) {
    return null;
  }
  try {
    const found = await navigator.serviceWorker.register(SW_URL, { scope: SW_SCOPE });
    await activated(found);
    return found as SyncRegistration;
  } catch {
    return null;
  }
}

/** Install the worker while the connection is good, so it is there when the connection is not. */
export function prepareBackgroundSync(): void {
  void registration();
}

/** Ask the browser to wake the worker once the connection is back, even with the app closed.
 * Chrome on Android does; elsewhere (Firefox, Safari) the open screen sends it instead. */
export async function requestBackgroundSync(): Promise<boolean> {
  const found = await registration();
  if (found?.sync === undefined) {
    return false;
  }
  try {
    await found.sync.register(OUTBOX_SYNC_TAG);
    return true;
  } catch {
    return false;
  }
}
