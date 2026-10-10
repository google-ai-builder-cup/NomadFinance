import type { Page } from "@playwright/test";

import type { TestUser } from "./emulators";
import { setDocument, updateDocument } from "./firestoreRest";

// The Contract Shield backend for the browser tests (NF-HR-004). The app uploads the file, asks
// for the analysis, and then reads the contract and its reports from Firestore, so this plays the
// backend's part on both sides: it answers the two calls and writes the documents the real
// pipeline writes (docs/data-model/collections/contracts.md). The contract is the Singapore
// sample of the backend's tests: one danger, caution and safe terms, and a complaint letter.

export interface ContractCall {
  method: string;
  path: string;
  body: unknown;
}

export interface ContractApiOptions {
  /** What step 2 reads from the contract. The worker's own choice still wins, as on the server. */
  detectedCountry?: string;
  /** `poor`: the photo is too unclear to analyse (the upload answers, the analysis does not run). */
  legibility?: "good" | "poor";
  /** The reader finds no document in the file (a photo of something else): the upload answers 422. */
  notADocument?: boolean;
}

export interface FakeContracts {
  calls: ContractCall[];
  /** The next analysis fails with this status (503: the AI service is busy); the one after works. */
  failNextAnalysis(status?: number): void;
  /** Every call fails as it does with no signal, until `connect()`. */
  disconnect(): void;
  connect(): void;
  to(method: string, pattern: RegExp): ContractCall[];
}

const DANGER = [
  [
    "recruitment_fees",
    "A placement loan is deducted from the salary.",
    "SGD 100 a month for 6 months.",
  ],
  [
    "rest_days_and_holidays",
    "Only one rest day a month.",
    "4 Rest days: one (1) rest day per month.",
  ],
  ["passport_retention", "The employer keeps the passport.", "6 Passport: kept by the employer."],
] as const;

function clauses(prefix: string) {
  const risks = ["safe", "caution", "danger", "danger", "caution", "danger"] as const;
  const categories = [
    "minimum_wage",
    "working_hours",
    DANGER[0][0],
    DANGER[1][0],
    "early_termination",
    DANGER[2][0],
  ] as const;
  return risks.map((risk, index) => ({
    index,
    number: String(index + 1),
    page: 1 + Math.floor(index / 3),
    text: `${prefix}Clause ${index + 1} of the sample contract.`,
    category: categories[index],
    risk,
    law_reference: "Employment of Foreign Manpower (Work Passes) Regulations 2012",
    explanation: `${prefix}${DANGER[index % 3][1]}`,
    recommendation: risk === "safe" ? null : `${prefix}Ask about this term before you sign.`,
    block_ids: [index + 1],
  }));
}

function report(language: string, translated: boolean) {
  const prefix = translated ? `[${language}] ` : "";
  return {
    language,
    is_source: !translated,
    full_text: `${prefix}EMPLOYMENT CONTRACT. The employer keeps the passport.`,
    summary: `${prefix}The employer keeps the passport and gives only one rest day a month.`,
    clauses: clauses(prefix),
    complaint: {
      template_type: "general",
      authority_name: "Ministry of Manpower (MOM)",
      authority_url: "https://www.mom.gov.sg",
      channels: [{ kind: "phone", value: "6438 5122", note: "Mon to Fri" }],
      letter_language: "en",
      letter_text: "To the labor authority: I am writing to report violations of my rights.",
      worker_language: language,
      worker_copy: null,
      violation_count: 3,
    },
    content_hash: "e2e-hash",
    law_version: 1,
    prompt_versions: { "contract.extract": 2, "contract.compare": 1 },
    models: { reasoning: "stand-in" },
  };
}

/**
 * A finished check with its reports already in every language, written the way the pipeline leaves
 * it, for the tests that only read it (the report screen, the history, the languages).
 */
export async function seedCompletedContract(
  user: TestUser,
  id = "e2eseeded0000001",
  languages: readonly string[] = ["bn", "en", "hi", "id", "ne", "tl"]
): Promise<string> {
  const path = `users/${user.uid}/contracts/${id}`;
  await setDocument(path, {
    status: "completed",
    title: "Employment contract",
    legibility: "good",
    mime_type: "application/pdf",
    size_bytes: 2048,
    page_count: 2,
    content_hash: `hash-${id}`,
    detected: { host_country: "SG", language: "en" },
    extracted: {
      employer_name: "Tan Wei Ming",
      salary_amount: 650,
      salary_currency: "SGD",
      salary_period: "month",
    },
    host_country: "SG",
    job_type: "domestic_worker",
    health_score: 25,
    risk_level: "danger",
    clause_counts: { safe: 1, caution: 2, danger: 3 },
    report_languages: [...languages].sort(),
    law_version: 1,
    prompt_versions: { "contract.extract": 2 },
    created_at: new Date(),
    updated_at: new Date(),
    schema_version: 1,
  });
  for (const language of languages) {
    await setDocument(`${path}/reports/${language}`, {
      ...report(language, language !== "en"),
      created_at: new Date(),
      schema_version: 1,
    });
  }
  return id;
}

const pause = (ms: number) => new Promise((resolve) => setTimeout(resolve, ms));

export async function contractApi(
  page: Page,
  user: TestUser,
  options: ContractApiOptions = {}
): Promise<FakeContracts> {
  const calls: ContractCall[] = [];
  const byFile = new Map<string, string>();
  const languages = new Map<string, Set<string>>();
  let failure: number | null = null;
  let offline = false;
  let count = 0;
  const path = (id: string) => `users/${user.uid}/contracts/${id}`;
  const stamp = () => ({ updated_at: new Date() });

  await page.route("**/api/v1/contracts**", async (route) => {
    if (offline) {
      return route.abort("internetdisconnected");
    }
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method();
    const raw = request.postData() ?? "";
    let body: unknown = raw;
    if ((request.headers()["content-type"] ?? "").includes("application/json") && raw !== "") {
      body = JSON.parse(raw);
    }
    const json = (status: number, payload: unknown) =>
      route.fulfill({
        status,
        contentType: "application/json",
        body: JSON.stringify(payload),
      });

    if (method === "POST" && url.pathname === "/api/v1/contracts") {
      calls.push({ method, path: url.pathname, body: "(file)" });
      if (options.notADocument) {
        return json(422, { detail: "The file does not appear to be a document." });
      }
      const file = /filename="([^"]+)"/.exec(raw)?.[1] ?? `contract-${count}.pdf`;
      const poor = options.legibility === "poor";
      const reused = byFile.get(file);
      if (reused) {
        return json(201, {
          contract_id: reused,
          status: "completed",
          reused: true,
          page_count: 2,
          title: "Employment contract",
          legibility: "good",
        });
      }
      const id = `e2econtract${String(++count).padStart(8, "0")}`;
      byFile.set(file, id);
      await setDocument(path(id), {
        status: "uploaded",
        title: "Employment contract",
        legibility: poor ? "poor" : "good",
        filename: file,
        mime_type: "application/pdf",
        size_bytes: 2048,
        page_count: 2,
        content_hash: `hash-${id}`,
        prompt_versions: { "contract.extract": 2 },
        created_at: new Date(),
        updated_at: new Date(),
        schema_version: 1,
      });
      return json(201, {
        contract_id: id,
        status: "uploaded",
        reused: false,
        page_count: 2,
        title: "Employment contract",
        legibility: poor ? "poor" : "good",
      });
    }

    const analyze = /^\/api\/v1\/contracts\/([^/]+)\/analyze$/.exec(url.pathname);
    if (method === "POST" && analyze) {
      calls.push({ method, path: url.pathname, body });
      const id = analyze[1];
      if (failure !== null) {
        const status = failure;
        failure = null;
        await updateDocument(path(id), {
          status: "failed",
          step: "compare",
          error: { step: "compare", code: "gemini_busy" },
          ...stamp(),
        });
        return json(status, { detail: "The AI service is busy." });
      }
      const choices = (body ?? {}) as {
        host_country?: string;
        job_type?: string;
        report_language?: string;
      };
      const language = choices.report_language ?? "en";
      await updateDocument(path(id), { status: "processing", step: "detect", ...stamp() });
      await pause(300);
      await updateDocument(path(id), { step: "compare", ...stamp() });
      await pause(300);
      const stored = new Set(["en", language]);
      languages.set(id, stored);
      await setDocument(`${path(id)}/reports/en`, {
        ...report("en", false),
        created_at: new Date(),
        schema_version: 1,
      });
      if (language !== "en") {
        await setDocument(`${path(id)}/reports/${language}`, {
          ...report(language, true),
          created_at: new Date(),
          schema_version: 1,
        });
      }
      const host = choices.host_country ?? options.detectedCountry ?? "SG";
      const analysis = {
        contract_id: id,
        status: "completed",
        cached: false,
        host_country: host,
        job_type: choices.job_type ?? "domestic_worker",
        health_score: 25,
        risk_level: "danger",
        clause_counts: { safe: 1, caution: 2, danger: 3 },
        report_language: language,
        report_languages: [...stored].sort(),
        complaint_pending: false,
        complaint_pending_reason: null,
      };
      await updateDocument(path(id), {
        status: "completed",
        host_country: analysis.host_country,
        job_type: analysis.job_type,
        health_score: analysis.health_score,
        risk_level: analysis.risk_level,
        clause_counts: analysis.clause_counts,
        report_languages: analysis.report_languages,
        detected: {
          host_country: options.detectedCountry ?? analysis.host_country,
          language: "en",
        },
        extracted: {
          employer_name: "Tan Wei Ming",
          salary_amount: 650,
          salary_currency: "SGD",
          salary_period: "month",
        },
        law_version: 1,
        ...stamp(),
      });
      return json(200, analysis);
    }

    const translate = /^\/api\/v1\/contracts\/([^/]+)\/reports\/([a-z]{2})$/.exec(url.pathname);
    if (method === "POST" && translate) {
      calls.push({ method, path: url.pathname, body });
      const [, id, language] = translate;
      const stored = languages.get(id) ?? new Set(["en"]);
      stored.add(language);
      languages.set(id, stored);
      await pause(300);
      await setDocument(`${path(id)}/reports/${language}`, {
        ...report(language, true),
        created_at: new Date(),
        schema_version: 1,
      });
      await updateDocument(path(id), { report_languages: [...stored].sort(), ...stamp() });
      return json(200, report(language, true));
    }
    return route.fallback();
  });

  return {
    calls,
    failNextAnalysis: (status = 503) => {
      failure = status;
    },
    disconnect: () => {
      offline = true;
    },
    connect: () => {
      offline = false;
    },
    to: (method, pattern) =>
      calls.filter((call) => call.method === method && pattern.test(call.path)),
  };
}
