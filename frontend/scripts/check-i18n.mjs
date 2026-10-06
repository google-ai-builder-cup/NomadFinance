// Fails when a language is missing a key that English has (NF-F0-013). English is the source of
// truth: every namespace is compared with its `en` file.
//
//   node scripts/check-i18n.mjs
//
// Namespaces: the shared strings are src/i18n/<lang>.json; every folder under src/i18n/ is a
// module namespace with src/i18n/<namespace>/<lang>.json. No dependencies, so CI runs it
// straight after `pnpm install`.

import { existsSync, readdirSync, readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));
const I18N_DIR = path.resolve(here, "../src/i18n");
const LANGUAGES_FILE = path.resolve(here, "../src/lib/languages.ts");
const SOURCE = "en";

/** The codes in SUPPORTED_LANGUAGES, read from the app's own list so there is one. */
export function readLanguages(file = LANGUAGES_FILE) {
  const codes = [...readFileSync(file, "utf8").matchAll(/code:\s*"([a-z]{2,3})"/g)].map(
    (match) => match[1]
  );
  if (!codes.includes(SOURCE)) {
    throw new Error(`Could not read the language codes from ${file}`);
  }
  return codes;
}

function leaves(node, prefix = "") {
  if (typeof node !== "object" || node === null || Array.isArray(node)) {
    return { [prefix]: node };
  }
  return Object.entries(node).reduce(
    (all, [key, value]) => ({ ...all, ...leaves(value, prefix ? `${prefix}.${key}` : key) }),
    {}
  );
}

// i18next picks plural forms by suffix, and languages differ in how many they have (Indonesian
// has only `_other`), so plural keys are compared by their base name.
const PLURAL_SUFFIX = /_(zero|one|two|few|many|other)$/;
const baseKey = (key) => key.replace(PLURAL_SUFFIX, "");

const placeholders = (text) =>
  [...text.matchAll(/{{\s*([^}\s,]+)[^}]*}}/g)]
    .map((match) => match[1])
    .sort()
    .join(",");

function namespaceFile(dir, namespace, language) {
  return namespace === "translation"
    ? path.join(dir, `${language}.json`)
    : path.join(dir, namespace, `${language}.json`);
}

function namespaces(dir) {
  const folders = readdirSync(dir, { withFileTypes: true })
    .filter((entry) => entry.isDirectory())
    .map((entry) => entry.name)
    .sort();
  return ["translation", ...folders];
}

function load(file, problems, namespace, language) {
  if (!existsSync(file)) {
    problems.push({ namespace, language, message: "file is missing" });
    return null;
  }
  try {
    return leaves(JSON.parse(readFileSync(file, "utf8")));
  } catch (error) {
    problems.push({ namespace, language, message: `not valid JSON (${error.message})` });
    return null;
  }
}

/**
 * Compare every namespace's files with its English file.
 * @returns {{ problems: {namespace: string, language: string, message: string}[], keys: number,
 *   namespaces: string[], languages: string[] }}
 */
export function checkI18n(dir = I18N_DIR, languages = readLanguages()) {
  const problems = [];
  const names = namespaces(dir);
  let keys = 0;

  for (const namespace of names) {
    const english = load(namespaceFile(dir, namespace, SOURCE), problems, namespace, SOURCE);
    if (english === null) continue;
    keys += Object.keys(english).length;
    const englishBases = new Set(Object.keys(english).map(baseKey));

    for (const [key, text] of Object.entries(english)) {
      if (typeof text !== "string") {
        problems.push({ namespace, language: SOURCE, message: `${key}: value is not a string` });
      }
    }

    for (const language of languages.filter((code) => code !== SOURCE)) {
      const translated = load(
        namespaceFile(dir, namespace, language),
        problems,
        namespace,
        language
      );
      if (translated === null) continue;
      const bases = new Set(Object.keys(translated).map(baseKey));

      for (const base of englishBases) {
        if (!bases.has(base)) {
          problems.push({ namespace, language, message: `missing key ${base}` });
        }
      }
      for (const base of bases) {
        if (!englishBases.has(base)) {
          problems.push({
            namespace,
            language,
            message: `key ${base} is not in English (the source of truth)`,
          });
        }
      }
      for (const [key, text] of Object.entries(translated)) {
        if (typeof text !== "string" || text.trim() === "") {
          problems.push({ namespace, language, message: `${key}: empty or not a string` });
        } else if (
          typeof english[key] === "string" &&
          placeholders(text) !== placeholders(english[key])
        ) {
          problems.push({
            namespace,
            language,
            message: `${key}: {{placeholders}} differ from English`,
          });
        }
      }
    }
  }
  return { problems, keys, namespaces: names, languages };
}

function main() {
  const { problems, keys, namespaces: names, languages } = checkI18n();
  if (problems.length === 0) {
    console.log(
      `i18n OK: ${names.length} namespaces (${names.join(", ")}) x ${languages.length} languages, ${keys} English keys`
    );
    return 0;
  }
  console.error(
    `i18n check failed: ${problems.length} problem(s). English is the source of truth.\n`
  );
  for (const { namespace, language, message } of problems) {
    console.error(`  ${namespace} / ${language}: ${message}`);
  }
  console.error("\nAdd the key to every language file (English first), or remove it from all.");
  return 1;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  process.exitCode = main();
}
