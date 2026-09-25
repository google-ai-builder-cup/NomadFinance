import en from "@/i18n/en.json";

type Messages = { [key: string]: string | Messages };
type Params = Record<string, string | number>;

// TODO(Aditya): replace with react-i18next and all 6 language files NF-P1-011
// Stand-in with the same key and {{param}} format as i18next, so call sites keep working.
export function translate(key: string, params?: Params): string {
  let node: string | Messages | undefined = en as Messages;
  for (const part of key.split(".")) {
    node = typeof node === "object" ? node[part] : undefined;
  }
  const template = typeof node === "string" ? node : key;
  return template.replace(/\{\{(\w+)\}\}/g, (match, name: string) =>
    params && name in params ? String(params[name]) : match
  );
}
