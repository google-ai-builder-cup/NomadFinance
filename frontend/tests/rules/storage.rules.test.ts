import { readFileSync } from "node:fs";

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment,
} from "@firebase/rules-unit-testing";
import { type FirebaseStorage, getMetadata, ref, uploadString } from "firebase/storage";
import { afterAll, beforeAll, describe, it } from "vitest";

// Runs against the Storage emulator via `pnpm test:rules` (firebase emulators:exec).
const RULES = readFileSync(new URL("../../storage.rules", import.meta.url), "utf8");

let env: RulesTestEnvironment;

function storage(uid: string | null): FirebaseStorage {
  const context = uid === null ? env.unauthenticatedContext() : env.authenticatedContext(uid);
  return context.storage() as unknown as FirebaseStorage;
}

const OWNED_FILES = [
  "contracts/alice/c1/contract.pdf",
  "bills/alice/b1/bill.jpg",
  "exports/alice/financial-identity-20260925.pdf",
];

beforeAll(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-nomadfinance",
    storage: { rules: RULES },
  });
  await env.withSecurityRulesDisabled(async (context) => {
    const admin = context.storage() as unknown as FirebaseStorage;
    for (const path of [...OWNED_FILES, "radar-evidence/r1/photo.jpg"]) {
      await uploadString(ref(admin, path), "demo");
    }
  });
});

afterAll(async () => {
  await env.clearStorage();
  await env.cleanup();
});

describe("storage.rules", () => {
  it.each(OWNED_FILES)("lets only the owner read %s", async (path) => {
    await assertSucceeds(getMetadata(ref(storage("alice"), path)));
    await assertFails(getMetadata(ref(storage("bob"), path)));
    await assertFails(getMetadata(ref(storage(null), path)));
  });

  it.each([
    "contracts/alice/c2/new.pdf",
    "bills/alice/b2/new.jpg",
    "exports/alice/fake.pdf",
    "contracts/bob/c1/planted.pdf",
  ])("blocks browser uploads to %s", async (path) => {
    await assertFails(uploadString(ref(storage("alice"), path), "data"));
  });

  it("denies radar evidence to everyone in the browser", async () => {
    await assertFails(getMetadata(ref(storage("alice"), "radar-evidence/r1/photo.jpg")));
  });
});
