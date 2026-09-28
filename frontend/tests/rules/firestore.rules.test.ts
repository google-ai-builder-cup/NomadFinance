import { readFileSync } from "node:fs";

import {
  assertFails,
  assertSucceeds,
  initializeTestEnvironment,
  type RulesTestEnvironment,
} from "@firebase/rules-unit-testing";
import {
  collection,
  deleteDoc,
  doc,
  type DocumentData,
  type Firestore,
  getDoc,
  getDocs,
  serverTimestamp,
  setDoc,
  Timestamp,
  updateDoc,
} from "firebase/firestore";
import { afterAll, beforeAll, beforeEach, describe, it } from "vitest";

// Runs against the Firestore emulator via `pnpm test:rules` (firebase emulators:exec).
const RULES = readFileSync(new URL("../../firestore.rules", import.meta.url), "utf8");

let env: RulesTestEnvironment;

const ALICE = "alice";
const BOB = "bob";

function db(uid: string | null): Firestore {
  const context = uid === null ? env.unauthenticatedContext() : env.authenticatedContext(uid);
  return context.firestore() as unknown as Firestore;
}

async function seed(path: string, data: DocumentData): Promise<void> {
  await env.withSecurityRulesDisabled(async (context) => {
    await setDoc(doc(context.firestore() as unknown as Firestore, path), data);
  });
}

function newProfile(overrides: DocumentData = {}): DocumentData {
  return {
    home_country: "IN",
    host_country: "SG",
    job_type: "domestic_worker",
    preferred_language: "hi",
    created_at: serverTimestamp(),
    updated_at: serverTimestamp(),
    schema_version: 1,
    ...overrides,
  };
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
    firestore: { rules: RULES },
  });
});

afterAll(async () => {
  await env.cleanup();
});

beforeEach(async () => {
  await env.clearFirestore();
});

describe("users/{uid}: create", () => {
  it("lets the owner create a valid profile", async () => {
    await assertSucceeds(setDoc(doc(db(ALICE), "users/alice"), newProfile()));
  });

  it("allows notification prefs and push tokens", async () => {
    const profile = newProfile({
      notification_prefs: { radar_alerts: true, radar_corridors: ["SG-IN"], reminders: false },
      fcm_tokens: ["token-1"],
    });
    await assertSucceeds(setDoc(doc(db(ALICE), "users/alice"), profile));
  });

  it("blocks creating someone else's profile", async () => {
    await assertFails(setDoc(doc(db(BOB), "users/alice"), newProfile()));
  });

  it("blocks signed-out users", async () => {
    await assertFails(setDoc(doc(db(null), "users/alice"), newProfile()));
  });

  it.each([
    ["a backdated created_at", { created_at: Timestamp.fromDate(new Date("2020-01-01")) }],
    ["a client-chosen updated_at", { updated_at: Timestamp.fromDate(new Date("2030-01-01")) }],
    ["schema_version 2", { schema_version: 2 }],
    ["an extra field", { is_admin: true }],
    ["host_country outside scope", { host_country: "US" }],
    ["home_country outside scope", { home_country: "US" }],
    ["unknown job_type", { job_type: "pilot" }],
    ["unsupported language", { preferred_language: "fr" }],
    ["more than 5 push tokens", { fcm_tokens: ["1", "2", "3", "4", "5", "6"] }],
    ["unknown notification pref", { notification_prefs: { marketing: true } }],
    ["non-boolean notification pref", { notification_prefs: { radar_alerts: "yes" } }],
    ["onboarding date that is not a timestamp", { onboarding_completed_at: "2026-09-26" }],
  ])("rejects %s", async (_label, overrides) => {
    await assertFails(setDoc(doc(db(ALICE), "users/alice"), newProfile(overrides)));
  });

  it("rejects a profile without created_at", async () => {
    const profile = newProfile();
    delete profile.created_at;
    await assertFails(setDoc(doc(db(ALICE), "users/alice"), profile));
  });
});

describe("users/{uid}: read, update, delete", () => {
  beforeEach(async () => {
    await seed("users/alice", SAVED_PROFILE);
  });

  it("lets only the owner read the profile", async () => {
    await assertSucceeds(getDoc(doc(db(ALICE), "users/alice")));
    await assertFails(getDoc(doc(db(BOB), "users/alice")));
    await assertFails(getDoc(doc(db(null), "users/alice")));
  });

  it("blocks listing all users", async () => {
    await assertFails(getDocs(collection(db(ALICE), "users")));
  });

  it("lets the owner update profile fields with a server updated_at", async () => {
    await assertSucceeds(
      updateDoc(doc(db(ALICE), "users/alice"), {
        host_country: "MY",
        onboarding_completed_at: serverTimestamp(),
        updated_at: serverTimestamp(),
      })
    );
  });

  it("requires updated_at to be refreshed", async () => {
    await assertFails(updateDoc(doc(db(ALICE), "users/alice"), { host_country: "MY" }));
  });

  it.each([
    ["created_at", { created_at: serverTimestamp() }],
    ["schema_version", { schema_version: 2 }],
    ["a new field", { role: "admin" }],
    ["an invalid value", { preferred_language: "fr" }],
  ])("blocks the owner changing %s", async (_label, change) => {
    await assertFails(
      updateDoc(doc(db(ALICE), "users/alice"), { ...change, updated_at: serverTimestamp() })
    );
  });

  it("blocks another user's update", async () => {
    await assertFails(
      updateDoc(doc(db(BOB), "users/alice"), { host_country: "MY", updated_at: serverTimestamp() })
    );
  });

  it("blocks deleting the profile from the browser", async () => {
    await assertFails(deleteDoc(doc(db(ALICE), "users/alice")));
  });
});

describe("users/{uid}: profile page edits (NF-P1-023)", () => {
  beforeEach(async () => {
    await seed("users/alice", SAVED_PROFILE);
  });

  it("lets the owner change all four details in one save", async () => {
    await assertSucceeds(
      updateDoc(doc(db(ALICE), "users/alice"), {
        preferred_language: "hi",
        host_country: "KR",
        home_country: "NP",
        job_type: "manufacturing_worker",
        updated_at: serverTimestamp(),
      })
    );
  });

  it("lets the owner save a complete notification map", async () => {
    await assertSucceeds(
      updateDoc(doc(db(ALICE), "users/alice"), {
        notification_prefs: {
          radar_alerts: true,
          reminders: false,
          radar_corridors: ["SG-IN", "AU-IN", "SG-PH", "MY-ID", "JP-PH", "AU-PH"],
        },
        updated_at: serverTimestamp(),
      })
    );
  });

  it.each([
    ["more than six corridors", { radar_corridors: ["1", "2", "3", "4", "5", "6", "7"] }],
    ["an unknown preference", { marketing: true }],
    ["a non-boolean reminder flag", { reminders: "yes" }],
  ])("rejects a notification map with %s", async (_label, prefs) => {
    await assertFails(
      updateDoc(doc(db(ALICE), "users/alice"), {
        notification_prefs: { radar_alerts: true, ...prefs },
        updated_at: serverTimestamp(),
      })
    );
  });
});

describe("users/{uid}/notifications", () => {
  const path = "users/alice/notifications/n1";

  beforeEach(async () => {
    await seed(path, {
      type: "radar_alert",
      title: "New alert",
      body: "3 reports this week",
      language: "en",
      read: false,
      created_at: Timestamp.now(),
      schema_version: 1,
    });
  });

  it("lets only the owner read", async () => {
    await assertSucceeds(getDoc(doc(db(ALICE), path)));
    await assertFails(getDoc(doc(db(BOB), path)));
  });

  it("lets the owner mark it read", async () => {
    await assertSucceeds(
      updateDoc(doc(db(ALICE), path), { read: true, read_at: serverTimestamp() })
    );
  });

  it("blocks changing anything else", async () => {
    await assertFails(updateDoc(doc(db(ALICE), path), { title: "Edited", read: true }));
  });

  it("blocks a non-boolean read flag", async () => {
    await assertFails(updateDoc(doc(db(ALICE), path), { read: "yes" }));
  });

  it("blocks creating and deleting notifications", async () => {
    await assertFails(
      setDoc(doc(db(ALICE), "users/alice/notifications/n2"), { title: "Fake", read: false })
    );
    await assertFails(deleteDoc(doc(db(ALICE), path)));
  });
});

describe("users/{uid} backend-written subcollections", () => {
  const paths = [
    "users/alice/contracts/c1",
    "users/alice/contracts/c1/reports/en",
    "users/alice/transfers/t1",
    "users/alice/income/i1",
    "users/alice/bills/b1",
    "users/alice/savings/s1",
    "users/alice/financial_profile/current",
  ];

  beforeEach(async () => {
    for (const path of paths) {
      await seed(path, { schema_version: 1 });
    }
    await seed("users/alice/private_backend_data/x", { secret: true });
    await seed("users/alice/contracts/c1/extraction/current", { text: "contract text" });
  });

  it.each(paths)("lets only the owner read %s", async (path) => {
    await assertSucceeds(getDoc(doc(db(ALICE), path)));
    await assertFails(getDoc(doc(db(BOB), path)));
    await assertFails(getDoc(doc(db(null), path)));
  });

  it.each(paths)("blocks the owner writing %s", async (path) => {
    await assertFails(setDoc(doc(db(ALICE), path), { schema_version: 1, amount: 1 }));
  });

  it("denies subcollections that aren't in the schema", async () => {
    await assertFails(getDoc(doc(db(ALICE), "users/alice/private_backend_data/x")));
  });

  it("keeps a contract's extraction backend-only, even from its owner (NF-P2-007)", async () => {
    await assertFails(getDoc(doc(db(ALICE), "users/alice/contracts/c1/extraction/current")));
    await assertFails(
      setDoc(doc(db(ALICE), "users/alice/contracts/c1/extraction/current"), { text: "x" })
    );
  });
});

describe("shared reference data", () => {
  const paths = [
    "corridors/SG-PH",
    "rates_cache/SGD_PHP",
    "rates_history/SGD_PHP",
    "rates_history/SGD_PHP/points/2026-09-25",
    "labor_laws/SG",
    "labor_laws/SG/_meta/current",
    "labor_laws/SG/rules/wages",
    "complaint_templates/SG",
    "complaint_templates/SG/types/unpaid_wages",
    "radar_entities/quickremit",
    "radar_alerts/SG-PH",
    "radar_alerts/SG-PH/current/a1",
  ];

  beforeEach(async () => {
    for (const path of paths) {
      await seed(path, { schema_version: 1 });
    }
  });

  it.each(paths)("lets any signed-in user read %s", async (path) => {
    await assertSucceeds(getDoc(doc(db(BOB), path)));
  });

  it.each(paths)("blocks signed-out reads of %s", async (path) => {
    await assertFails(getDoc(doc(db(null), path)));
  });

  it.each(paths)("blocks browser writes to %s", async (path) => {
    await assertFails(setDoc(doc(db(ALICE), path), { tampered: true }));
  });
});

describe("backend-only and unknown collections", () => {
  it.each(["radar_reports/r1", "report_embeddings/r1", "admin/config"])(
    "denies %s to signed-in users",
    async (path) => {
      await seed(path, { schema_version: 1 });
      await assertFails(getDoc(doc(db(ALICE), path)));
      await assertFails(setDoc(doc(db(ALICE), path), { schema_version: 1 }));
    }
  );
});
