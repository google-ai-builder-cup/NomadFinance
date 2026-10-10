import { FIRESTORE_URL, PROJECT_ID } from "./emulators";

// The app reads the worker's contracts and Financial Identity straight from Firestore, and only
// the backend writes them. These tests have no backend, so they play its part: a document is
// written with the emulator's admin token, which skips the security rules, exactly as the
// backend's own writes do. Nothing here reaches real Firebase (the project is `demo-`).

export type FirestoreValue =
  null | string | number | boolean | Date | FirestoreValue[] | { [key: string]: FirestoreValue };

type WireValue = Record<string, unknown>;

function toWire(value: FirestoreValue): WireValue {
  if (value === null) {
    return { nullValue: null };
  }
  if (typeof value === "string") {
    return { stringValue: value };
  }
  if (typeof value === "boolean") {
    return { booleanValue: value };
  }
  if (typeof value === "number") {
    return Number.isInteger(value) ? { integerValue: String(value) } : { doubleValue: value };
  }
  if (value instanceof Date) {
    return { timestampValue: value.toISOString() };
  }
  if (Array.isArray(value)) {
    return { arrayValue: { values: value.map(toWire) } };
  }
  return { mapValue: { fields: toFields(value) } };
}

function toFields(data: { [key: string]: FirestoreValue }): Record<string, WireValue> {
  return Object.fromEntries(Object.entries(data).map(([key, value]) => [key, toWire(value)]));
}

const DOCUMENTS = `${FIRESTORE_URL}/v1/projects/${PROJECT_ID}/databases/(default)/documents`;
const ADMIN = { "Content-Type": "application/json", Authorization: "Bearer owner" };

/** Writes (replaces) the document at `path`, for example `users/{uid}/contracts/{id}`. */
export async function setDocument(
  path: string,
  data: { [key: string]: FirestoreValue }
): Promise<void> {
  const response = await fetch(`${DOCUMENTS}/${path}`, {
    method: "PATCH",
    headers: ADMIN,
    body: JSON.stringify({ fields: toFields(data) }),
  });
  if (!response.ok) {
    throw new Error(`The Firestore emulator refused ${path} (${response.status}). Is it running?`);
  }
}

/** Changes only the named top-level fields of an existing document. */
export async function updateDocument(
  path: string,
  data: { [key: string]: FirestoreValue }
): Promise<void> {
  const mask = Object.keys(data)
    .map((key) => `updateMask.fieldPaths=${encodeURIComponent(key)}`)
    .join("&");
  const response = await fetch(`${DOCUMENTS}/${path}?${mask}`, {
    method: "PATCH",
    headers: ADMIN,
    body: JSON.stringify({ fields: toFields(data) }),
  });
  if (!response.ok) {
    throw new Error(`The Firestore emulator refused the update of ${path} (${response.status}).`);
  }
}
