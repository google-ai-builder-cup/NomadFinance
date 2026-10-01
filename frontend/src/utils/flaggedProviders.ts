import type { RadarEntityProfile } from "@/types/radar";
import { slugify } from "@/utils/slug";

/**
 * The flagged radar profile for a provider of the comparison, or null.
 *
 * Only a money transfer operator the community has flagged counts (`flagged`: two or more
 * distinct incidents, a pattern rather than one unverified report). A match is the provider's
 * slug against the profile's slug, or against a slug of one of its `aliases` (the documented
 * fix for a spelling the plain slug misses). An employer or agency that happens to share the
 * name never matches, and a profile that was never flagged shows nothing.
 */
export function findFlaggedEntity(
  firm: string,
  entities: readonly RadarEntityProfile[]
): RadarEntityProfile | null {
  const slug = slugify(firm);
  if (slug === "") {
    return null;
  }
  return (
    entities.find(
      (entity) =>
        entity.flagged &&
        entity.entity_type === "money_transfer_operator" &&
        (entity.slug === slug || (entity.aliases ?? []).some((alias) => slugify(alias) === slug))
    ) ?? null
  );
}
