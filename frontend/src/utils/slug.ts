/**
 * The id of a `radar_entities` document from a business name: lowercase words joined by single
 * hyphens, accents dropped. Must give what the backend's `app/utils/slugs.py` (python-slugify)
 * gives for the same Latin-script name, because the slug is the join key between a provider in
 * the comparison and its radar profile (docs/data-model/collections/radar.md). Names in other
 * scripts are not transliterated here: they come out empty and never match.
 */
export function slugify(name: string): string {
  return name
    .normalize("NFKD")
    .replace(/[̀-ͯ]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
}
