import { ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { useI18n } from "@/hooks/useI18n";
import { useFlaggedProvider } from "@/hooks/useRadar";

export interface FlaggedProviderBadgeProps {
  /** The provider's name as the comparison shows it (`ProviderResult.firm`). */
  firm: string;
}

/**
 * "Community flagged" next to a provider that workers have reported (NF-P3-022, the Radar →
 * Remittance link of the cross-pillar flow). Links to the business's radar profile. Renders
 * nothing for a provider with no flagged profile, so it is safe to put beside every name.
 */
export default function FlaggedProviderBadge({ firm }: FlaggedProviderBadgeProps) {
  const { t } = useI18n();
  const entity = useFlaggedProvider(firm);
  if (entity === null) {
    return null;
  }
  const detail = t("remittance.flagged.detail", { firm, number: String(entity.report_count) });

  return (
    <Link
      to={`/radar/entity/${entity.slug}`}
      title={detail}
      aria-label={detail}
      className="inline-flex items-center gap-1 rounded-full bg-destructive/10 px-2 py-0.5 text-xs font-semibold text-destructive hover:bg-destructive/20 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-destructive"
    >
      <ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />
      {t("remittance.flagged.label")}
    </Link>
  );
}
