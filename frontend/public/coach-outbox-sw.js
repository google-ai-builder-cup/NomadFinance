// Delivers an answer the Coach screen could not send because there was no connection (NF-FC-019).
//
// The screen keeps the answer in IndexedDB and asks the browser for a Background Sync (tag
// "coach-outbox"). When the connection is back the browser wakes this worker, even with the app
// closed, and it sends the answer with the same Idempotency-Key the screen used, so the server
// runs the turn once whoever sends it. Background Sync exists in Chrome on Android; elsewhere the
// open screen sends the answer itself.
//
// Registered on its own scope (lib/coachOutboxStore.ts), not "/": the app's own service worker
// owns "/", and this one never answers a page's requests. A static file in public/, so it is
// plain JavaScript and repeats the names in src/utils/coachStorageKeys.ts; a test checks them.
//
// It only sends with a token that still has time on it. A token that has lapsed is left for the
// screen, which signs the request itself the next time the app opens: the answer is never lost,
// only later.

const DB_NAME = "nomadfinance-coach-outbox";
const DB_VERSION = 1;
const STORE = "entries";
const SYNC_TAG = "coach-outbox";
const LEASE_MS = 90000;
const MAX_AGE_MS = 14 * 24 * 60 * 60 * 1000;
const TOKEN_MARGIN_MS = 60000;
// A turn takes 20 to 60 seconds on the reasoning tier; the server gives up on one after 90.
const SEND_TIMEOUT_MS = 75000;

self.addEventListener("install", () => self.skipWaiting());

self.addEventListener("sync", (event) => {
  if (event.tag === SYNC_TAG) {
    event.waitUntil(flush());
  }
});

function openDb() {
  return new Promise((resolve, reject) => {
    const request = self.indexedDB.open(DB_NAME, DB_VERSION);
    request.onupgradeneeded = () => {
      request.result.createObjectStore(STORE, { keyPath: "id" });
    };
    request.onsuccess = () => resolve(request.result);
    request.onerror = () => reject(request.error);
  });
}

// One transaction: `work` may read and then write, and nothing can get in between.
async function inStore(mode, work) {
  const db = await openDb();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, mode);
      let value;
      work(tx.objectStore(STORE), (found) => {
        value = found;
      });
      tx.oncomplete = () => resolve(value);
      tx.onerror = tx.onabort = () => reject(tx.error);
    });
  } finally {
    db.close();
  }
}

function allEntries() {
  return inStore("readonly", (store, done) => {
    const request = store.getAll();
    request.onsuccess = () => done(request.result);
  });
}

// Take the answer to send it, unless the screen (or an earlier run of this worker) holds it.
function claim(id, now) {
  return inStore("readwrite", (store, done) => {
    const request = store.get(id);
    request.onsuccess = () => {
      const entry = request.result;
      if (!entry) {
        done(null);
      } else if (entry.claim && now - entry.claim.at < LEASE_MS) {
        done(null);
      } else {
        const next = { ...entry, claim: { by: "sw", at: now } };
        store.put(next);
        done(next);
      }
    };
  });
}

function change(id, edit) {
  return inStore("readwrite", (store, done) => {
    const request = store.get(id);
    request.onsuccess = () => {
      if (request.result) {
        store.put(edit(request.result));
      }
      done();
    };
  });
}

const release = (id) => change(id, (entry) => ({ ...entry, claim: null }));
const reject = (id, code) => change(id, (entry) => ({ ...entry, claim: null, rejected: code }));
const remove = (id) =>
  inStore("readwrite", (store, done) => {
    store.delete(id);
    done();
  });

async function errorCode(response) {
  try {
    const body = await response.json();
    return typeof body.code === "string" ? body.code : "";
  } catch {
    return "";
  }
}

// What happened to one send: "delivered", "retry" (try again later), "wait" (the screen has to do
// it) or "rejected" (the server will never take it).
async function send(entry) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), SEND_TIMEOUT_MS);
  try {
    const response = await self.fetch(entry.url, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${entry.token}`,
        "Content-Type": "application/json",
        Accept: "text/event-stream",
        "Idempotency-Key": entry.idempotencyKey,
      },
      body: JSON.stringify({ text: entry.text, language: entry.language }),
      signal: controller.signal,
    });
    if (response.ok) {
      // The turn is saved when the stream says `done`; reading it to the end also keeps the
      // server from cancelling the turn on a closed connection.
      const stream = await response.text();
      return { kind: /(?:^|\n)event: ?done\r?\n/.test(stream) ? "delivered" : "retry" };
    }
    if (response.status === 401) {
      return { kind: "wait" };
    }
    const code = await errorCode(response);
    if (
      response.status === 429 ||
      response.status >= 500 ||
      code === "request_in_progress" ||
      code === "turn_in_progress"
    ) {
      return { kind: "retry" };
    }
    return { kind: "rejected", code: code || `http_${response.status}` };
  } catch {
    return { kind: "retry" };
  } finally {
    clearTimeout(timer);
  }
}

async function flush() {
  const entries = (await allEntries()).sort((a, b) => a.queuedAt - b.queuedAt);
  let again = false;
  for (const entry of entries) {
    const now = Date.now();
    if (now - entry.queuedAt > MAX_AGE_MS) {
      await remove(entry.id);
    } else if (
      !entry.rejected &&
      entry.token &&
      entry.tokenExpiresAt &&
      entry.tokenExpiresAt - now >= TOKEN_MARGIN_MS
    ) {
      const mine = await claim(entry.id, now);
      if (mine === null) {
        // The screen is sending it, or just did. If it is still here later, try again.
        again = true;
        continue;
      }
      const outcome = await send(mine);
      if (outcome.kind === "delivered") {
        await remove(mine.id);
      } else if (outcome.kind === "rejected") {
        await reject(mine.id, outcome.code);
      } else {
        await release(mine.id);
        again = again || outcome.kind === "retry";
      }
    }
  }
  if (again) {
    // A failed sync is run again by the browser, a few times and later each time.
    throw new Error("coach-outbox: some answers are still waiting");
  }
}
