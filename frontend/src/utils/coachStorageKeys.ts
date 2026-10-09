// Names of what the Coach keeps on the worker's phone (NF-FC-019). They sit in a module of their
// own so that signing out can wipe them without pulling the Coach's code into the main bundle.
// `public/coach-outbox-sw.js` is plain JavaScript and repeats the database's names; a test loads
// that file and checks it against these.

export const OUTBOX_DB_NAME = "nomadfinance-coach-outbox";
export const OUTBOX_DB_VERSION = 1;
export const OUTBOX_STORE = "entries";
export const OUTBOX_SYNC_TAG = "coach-outbox";
export const DRAFT_KEY_PREFIX = "nomadfinance.coach.draft.";
