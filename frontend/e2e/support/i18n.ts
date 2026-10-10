import { readFileSync } from "node:fs";
import path from "node:path";

// The app's own strings, read from src/i18n for the tests that look at every language. `pnpm
// test:e2e` runs from frontend/, so the folder is found from the working directory.
const ROOT = path.resolve(process.cwd(), "src/i18n");

export const LANGUAGES = ["en", "hi", "tl", "id", "ne", "bn"] as const;
export type Language = (typeof LANGUAGES)[number];

type Tree = { [key: string]: Tree | string };

function load(file: string): Tree {
  return JSON.parse(readFileSync(path.join(ROOT, file), "utf8")) as Tree;
}

function find(tree: Tree, key: string): string {
  let node: Tree | string = tree;
  for (const part of key.split(".")) {
    node = typeof node === "string" ? node : node[part];
  }
  if (typeof node !== "string") {
    throw new Error(`There is no string "${key}" in the translations.`);
  }
  return node;
}

/** A shared string (`src/i18n/<language>.json`), for example `contract.upload.title`. */
export function appText(language: Language, key: string): string {
  return find(load(`${language}.json`), key);
}

/** A string of the Coach's own namespace (`src/i18n/coach/<language>.json`). */
export function coachString(language: Language, key: string): string {
  return find(load(`coach/${language}.json`), key);
}

function flatten(tree: Tree, prefix = ""): string[] {
  return Object.entries(tree).flatMap(([name, value]) => {
    const key = prefix === "" ? name : `${prefix}.${name}`;
    return typeof value === "string" ? [key] : flatten(value, key);
  });
}

/**
 * Every key of every namespace, as the app writes it. A screen that shows one of them instead of
 * the sentence it stands for has lost a translation. Short keys are left out: they could be words.
 */
export function allKeys(): string[] {
  return [
    ...flatten(load("en.json")),
    ...flatten(load("coach/en.json")),
    ...flatten(load("scam/en.json")),
  ].filter((key) => key.includes(".") && key.length > 8);
}
