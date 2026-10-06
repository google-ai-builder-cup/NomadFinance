// Commit message policy (NF-F0-009). Checked by the commit-msg hook in .pre-commit-config.yaml
// and again over every commit of a pull request by .github/workflows/commit-policy.yml.
//
// No `extends`: every rule is written out so the policy reads in one place and needs only
// @commitlint/cli, pinned in both callers.

// The only trailer a commit may carry, e.g. `Refs: NF-F0-009` or `Refs: NF-F0-009, NF-P4-004`.
const REFS = /^Refs: NF-[A-Z0-9]{2}-\d{3}(, NF-[A-Z0-9]{2}-\d{3})*$/;

// Anything shaped like a git trailer: `Key: value` or `Key #123`.
const TRAILER_SHAPE = /^([A-Za-z][A-Za-z0-9_-]*)(?::\s|\s#)/;

// Allow-list, not block-list: the config names no author, tool or service to forbid. It rejects
// every trailer except `Refs:`, so Co-authored-by, Signed-off-by, Generated-by, session links
// and whatever tool adds next year are all refused without being listed.
//
// Looks at the last paragraph (where trailers live; the repo writes `Refs:` straight under the
// subject, so that paragraph can be the whole body) and at any hyphenated `Some-Key:` line
// anywhere in the body, so a trailer cannot hide above a closing sentence.
function trailerAllowList(parsed) {
  const lines = (parsed.raw || "").replace(/\r\n/g, "\n").split("\n").slice(1);
  while (lines.length > 0 && lines[lines.length - 1].trim() === "") lines.pop();

  let lastParagraphStart = lines.length;
  while (lastParagraphStart > 0 && lines[lastParagraphStart - 1].trim() !== "") {
    lastParagraphStart -= 1;
  }

  for (let i = 0; i < lines.length; i += 1) {
    const line = lines[i];
    const shape = TRAILER_SHAPE.exec(line);
    if (!shape) continue;
    const inLastParagraph = i >= lastParagraphStart;
    if (!inLastParagraph && !shape[1].includes("-")) continue;
    if (shape[1] === "Refs" && REFS.test(line)) continue;
    const key = shape[1];
    return [
      false,
      key === "Refs"
        ? `"${line}" is not a valid Refs trailer: write "Refs: NF-XXX-NNN" (comma-separated for several)`
        : `trailer "${key}:" is not allowed: the only trailer is "Refs: NF-XXX-NNN"`,
    ];
  }
  return [true];
}

module.exports = {
  rules: {
    "type-empty": [2, "never"],
    "type-case": [2, "always", "lower-case"],
    "type-enum": [
      2,
      "always",
      ["feat", "fix", "docs", "chore", "refactor", "perf", "test", "build", "ci", "style", "revert"],
    ],
    "scope-empty": [2, "never"],
    "scope-case": [2, "always", "kebab-case"],
    "subject-empty": [2, "never"],
    "subject-full-stop": [2, "never", "."],
    "subject-case": [2, "never", ["sentence-case", "start-case", "pascal-case", "upper-case"]],
    "header-max-length": [2, "always", 72],
    "trailer-allow-list": [2, "always"],
  },
  plugins: [{ rules: { "trailer-allow-list": trailerAllowList } }],
  // `Merge ...` and `Revert ...` messages made by git or GitHub are skipped by commitlint's
  // defaults, which are left on.
};
