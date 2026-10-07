// axe for the tests of the scam screens (NF-SA-019). Only tests import this module; the app never
// does, and `axe-core` is a development dependency.
//
// jsdom has no layout engine, so what axe needs boxes and real colours for cannot be judged here:
// colour contrast and the size of a tap target. Those are measured in a real browser (see
// docs/runbooks/NF-SA-019-scam-i18n-a11y.md); everything else axe knows runs on every screen.
import axe from "axe-core";

const NEEDS_A_REAL_BROWSER = ["color-contrast", "target-size"] as const;

// A screen is drawn without the app shell, which supplies the page's landmark and its first
// heading, so the rules about the page as a whole cannot pass on a screen alone.
const NEEDS_THE_WHOLE_PAGE = ["region", "landmark-one-main", "page-has-heading-one"] as const;

const IMPACTS = ["minor", "moderate", "serious", "critical"] as const;
export type Impact = (typeof IMPACTS)[number];

const rank = (impact: Impact): number => IMPACTS.indexOf(impact);

const disabled = Object.fromEntries(
  [...NEEDS_A_REAL_BROWSER, ...NEEDS_THE_WHOLE_PAGE].map((rule) => [rule, { enabled: false }])
);

/** What axe finds wrong inside `root`, one readable line per failing element, at `minimum`
 * severity or worse. The tracker's bar is serious and critical, so that is the default. An empty
 * list is a pass; a failure prints which rule, how bad, and the element. */
export async function axeViolations(
  root: Element = document.body,
  minimum: Impact = "serious"
): Promise<string[]> {
  const { violations } = await axe.run(root, { rules: disabled, resultTypes: ["violations"] });
  return violations
    .filter((violation) => violation.impact != null && rank(violation.impact) >= rank(minimum))
    .flatMap((violation) =>
      violation.nodes.map(
        (node) =>
          `${violation.id} [${violation.impact}] ${violation.help}: ${node.html.slice(0, 160)}`
      )
    );
}

// What i18next shows when a key has no string: the key itself. The first part of every key in the
// app's two namespaces, so a version number or an address in a message is never taken for one.
const KEY_ROOTS =
  "home|input|screenshot|analyze|result|history|report|radarReport|common|errors|radar|nav";
const RAW_KEY = new RegExp(`^(${KEY_ROOTS})(\\.[A-Za-z0-9_]+)+$`);

const NAMED_BY_ATTRIBUTE = ["aria-label", "title", "placeholder", "alt"] as const;

/** Every text and accessible name inside `root` that is an i18n key shown as it is, which is what
 * a worker sees when a string is missing in their language. */
export function rawKeysShown(root: Element = document.body): string[] {
  const found: string[] = [];
  const walker = document.createTreeWalker(root, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node !== null; node = walker.nextNode()) {
    const text = node.textContent?.trim() ?? "";
    if (RAW_KEY.test(text)) {
      found.push(text);
    }
  }
  for (const element of root.querySelectorAll("*")) {
    for (const name of NAMED_BY_ATTRIBUTE) {
      const value = element.getAttribute(name)?.trim() ?? "";
      if (RAW_KEY.test(value)) {
        found.push(`${name}="${value}"`);
      }
    }
  }
  return found;
}
