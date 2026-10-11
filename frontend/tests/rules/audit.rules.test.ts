import { readFileSync } from "node:fs";

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment,
} from "@firebase/rules-unit-testing";
import {
  collection,
  collectionGroup,
  deleteDoc,
  doc,
  type DocumentData,
  type Firestore,
  getDocs,
  serverTimestamp,
  setDoc,
  Timestamp,
  updateDoc,
} from "firebase/firestore";
import { deleteObject, type FirebaseStorage, listAll, ref, uploadString } from "firebase/storage";
import { afterAll, beforeAll, beforeEach, describe, it } from "vitest";

// Security audit (NF-P4-004): what the per-path tests do not reach. Cross-user LIST and
// collection-group queries, and writes that look harmless but change what the rules protect.
// Runs against the emulators via `pnpm test:rules`.
const FIRESTORE_RULES = readFileSync(new URL("../../firestore.rules", import.meta.url), "utf8");
const STORAGE_RULES = readFileSync(new URL("../../storage.rules", import.meta.url), "utf8");

let env: RulesTestEnvironment;

const ALICE = "alice";
const BOB = "bob";

function db(uid: string | null): Firestore {
  const context = uid === null ? env.unauthenticatedContext() : env.authenticatedContext(uid);
  return context.firestore() as unknown as Firestore;
}

function storage(uid: string | null): FirebaseStorage {
  const context = uid === null ? env.unauthenticatedContext() : env.authenticatedContext(uid);
  return context.storage() as unknown as FirebaseStorage;
}

async function seed(path: string, data: DocumentData): Promise<void> {
  await env.withSecurityRulesDisabled(async (context) => {
    await setDoc(doc(context.firestore() as unknown as Firestore, path), data);
  });
}

const SAVED_PROFILE = {
  home_country: "IN",
  host_country: "SG",
  job_type: "domestic_worker",
  preferred_language: "hi",
  created_at: Timestamp.fromDate(new Date("2026-09-26T09:10:31Z")),
  updated_at: Timestamp.fromDate(new Date("2026-09-26T09:10:31Z")),
  schema_version: 1,
};

beforeAll(async () => {
  env = await initializeTestEnvironment({
    projectId: "demo-nomadfinance",
    firestore: { rules: FIRESTORE_RULES },
    storage: { rules: STORAGE_RULES },
  });
});

afterAll(async () => {
  await env.cleanup();
});

beforeEach(async () => {
  await env.clearFirestore();
});

describe("collection-group queries", () => {
  // A collection-group query reads that subcollection across every user, so one missing
  // `{path=**}` rule would expose everyone's data at once.
  const userGroups = [
    "notifications",
    "contracts",
    "reports",
    "extraction",
    "transfers",
    "income",
    "bills",
    "savings",
    "financial_profile",
    "coach_sessions",
    "coach_plans",
    "translations",
    "scam_checks",
  ];
  const sharedGroups = [
    "rules",
    "points",
    "current",
    "types",
    "_meta",
    "scam_taxonomy",
    "scam_patterns",
    "scam_indicators",
    "cost_baselines",
    "config",
    "gemini_usage",
  ];

  beforeEach(async () => {
    await seed("users/alice/notifications/n1", { title: "private" });
    await seed("users/alice/contracts/c1", { employer: "private" });
    await seed("users/alice/contracts/c1/reports/en", { summary: "private" });
    await seed("users/alice/contracts/c1/extraction/current", { text: "private" });
    await seed("users/alice/transfers/t1", { amount: 1 });
    await seed("users/alice/income/i1", { amount: 1 });
    await seed("users/alice/bills/b1", { amount: 1 });
    await seed("users/alice/savings/s1", { amount: 1 });
    await seed("users/alice/financial_profile/current", { score: 1 });
    await seed("labor_laws/SG/rules/wages", { rule: 1 });
    await seed("rates_history/SGD_PHP/points/p1", { rate: 1 });
    await seed("radar_alerts/SG-PH/current/a1", { entity: "x" });
    await seed("complaint_templates/SG/types/t1", { body: "x" });
    await seed("labor_laws/SG/_meta/current", { version: 1 });
    await seed("users/alice/coach_sessions/s1", { transcript: "private" });
    await seed("users/alice/coach_plans/p1", { departure_date: "2026-12-01" });
    await seed("users/alice/coach_plans/p1/translations/hi", { plan: "private" });
    await seed("users/alice/scam_checks/k1", { redacted_text: "private" });
    await seed("scam_taxonomy/fake_job_offer", { kind: "type" });
    await seed("scam_patterns/p-en-001", { text: "template" });
    await seed("scam_indicators/i1", { value: "private" });
    await seed("cost_baselines/SG", { currency: "SGD" });
    await seed("config/feature_flags", { flags: {} });
    await seed("gemini_usage/2026-11-12", { calls: {} });
  });

  it.each([...userGroups, ...sharedGroups])(
    "denies a collection-group query on %s to the owner, other users and signed-out callers",
    async (group) => {
      await assertFails(getDocs(collectionGroup(db(ALICE), group)));
      await assertFails(getDocs(collectionGroup(db(BOB), group)));
      await assertFails(getDocs(collectionGroup(db(null), group)));
    }
  );
});

describe("list queries on another user's data", () => {
  const kinds = ["notifications", "contracts", "transfers", "income", "bills", "savings"];

  beforeEach(async () => {
    for (const kind of kinds) {
      await seed(`users/alice/${kind}/x1`, { schema_version: 1 });
    }
    await seed("users/alice/contracts/c1/reports/en", { schema_version: 1 });
  });

  it.each(kinds)("lets the owner list %s but nobody else", async (kind) => {
    await assertSucceeds(getDocs(collection(db(ALICE), `users/alice/${kind}`)));
    await assertFails(getDocs(collection(db(BOB), `users/alice/${kind}`)));
    await assertFails(getDocs(collection(db(null), `users/alice/${kind}`)));
  });

  it("denies listing another user's contract reports", async () => {
    await assertSucceeds(getDocs(collection(db(ALICE), "users/alice/contracts/c1/reports")));
    await assertFails(getDocs(collection(db(BOB), "users/alice/contracts/c1/reports")));
  });

  it("denies listing every profile", async () => {
    await seed("users/alice", SAVED_PROFILE);
    await assertFails(getDocs(collection(db(BOB), "users")));
    await assertFails(getDocs(collection(db(ALICE), "users")));
  });
});

describe("collections the browser never reads", () => {
  it("denies listing them even to a signed-in user", async () => {
    await seed("radar_reports/r1", { reporter_hash: "secret" });
    await seed("report_embeddings/r1", { embedding: [1] });
    await assertFails(getDocs(collection(db(ALICE), "radar_reports")));
    await assertFails(getDocs(collection(db(ALICE), "report_embeddings")));
  });
});

describe("notifications belong to their owner", () => {
  beforeEach(async () => {
    await seed("users/alice/notifications/n1", {
      title: "t",
      read: false,
      created_at: Timestamp.now(),
    });
  });

  it("blocks another user marking it read or deleting it", async () => {
    await assertFails(updateDoc(doc(db(BOB), "users/alice/notifications/n1"), { read: true }));
    await assertFails(deleteDoc(doc(db(BOB), "users/alice/notifications/n1")));
    await assertFails(deleteDoc(doc(db(null), "users/alice/notifications/n1")));
  });

  it("blocks the owner rewriting the text a notification shows", async () => {
    await assertFails(updateDoc(doc(db(ALICE), "users/alice/notifications/n1"), { title: "x" }));
    await assertFails(
      updateDoc(doc(db(ALICE), "users/alice/notifications/n1"), { read: true, deep_link: "/x" })
    );
  });
});

describe("a profile update cannot change what the rules protect", () => {
  beforeEach(async () => {
    await seed("users/alice", SAVED_PROFILE);
  });

  it.each([
    ["an unknown field", { is_admin: true }],
    ["created_at", { created_at: Timestamp.fromDate(new Date("2020-01-01")) }],
    ["schema_version", { schema_version: 2 }],
    ["a stored uid", { uid: "bob" }],
  ])("rejects an update that adds or changes %s", async (_label, change) => {
    await assertFails(
      updateDoc(doc(db(ALICE), "users/alice"), { ...change, updated_at: serverTimestamp() })
    );
  });

  it("rejects a merge write by another user", async () => {
    await assertFails(
      setDoc(
        doc(db(BOB), "users/alice"),
        { host_country: "KR", updated_at: serverTimestamp() },
        { merge: true }
      )
    );
  });

  it("rejects another user's otherwise valid update", async () => {
    await assertFails(
      updateDoc(doc(db(BOB), "users/alice"), { host_country: "KR", updated_at: serverTimestamp() })
    );
  });
});

describe("storage: listing, deleting and overwriting", () => {
  beforeAll(async () => {
    await env.withSecurityRulesDisabled(async (context) => {
      const admin = context.storage() as unknown as FirebaseStorage;
      await uploadString(ref(admin, "contracts/alice/c1/contract.pdf"), "demo");
      await uploadString(ref(admin, "radar-evidence/r1/photo.jpg"), "demo");
    });
  });

  it("lets the owner list their folder but nobody else", async () => {
    await assertSucceeds(listAll(ref(storage(ALICE), "contracts/alice")));
    await assertFails(listAll(ref(storage(BOB), "contracts/alice")));
    await assertFails(listAll(ref(storage(null), "contracts/alice")));
  });

  it("does not let anyone list the top-level folders or the evidence folder", async () => {
    await assertFails(listAll(ref(storage(ALICE), "contracts")));
    await assertFails(listAll(ref(storage(ALICE), "radar-evidence")));
    await assertFails(listAll(ref(storage(ALICE), "radar-evidence/r1")));
  });

  it("blocks deleting files, including the owner's own", async () => {
    await assertFails(deleteObject(ref(storage(ALICE), "contracts/alice/c1/contract.pdf")));
    await assertFails(deleteObject(ref(storage(BOB), "contracts/alice/c1/contract.pdf")));
  });
});
