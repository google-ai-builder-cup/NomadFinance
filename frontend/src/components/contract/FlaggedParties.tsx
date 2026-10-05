import { ShieldAlert } from "lucide-react";
import { Link } from "react-router-dom";

import { useI18n } from "@/hooks/useI18n";
import { useFlaggedParties } from "@/hooks/useRadar";

export interface FlaggedPartiesProps {
  contractId: string;
}

/**
 * "Community flagged — N reports" for the employer or agency this contract names, when
 * Exploitation Radar has flagged them (NF-P3-023, the Radar → Contract Shield link of the
 * cross-pillar flow). Each warning links to the business's radar profile. Renders nothing when
 * no one is flagged or the lookup has not finished, so the report never waits for it.
 */
export default function FlaggedParties({ contractId }: FlaggedPartiesProps) {
  const { t } = useI18n();
  const parties = useFlaggedParties(contractId);
  if (parties.length === 0) {
    return null;
  }

  return (
    <ul aria-label={t("contract.flagged.listLabel")} className="space-y-2">
      {parties.map(({ role, name, entity }) => {
        const number = String(entity.report_count);
        const detail = t("contract.flagged.detail", { name, number });
        return (
          <li
            key={role}
            className="flex flex-wrap items-center gap-x-3 gap-y-1 rounded-xl border border-danger/30 bg-danger-tint p-3 text-sm"
          >
            <Link
              to={`/radar/entity/${entity.slug}`}
              title={detail}
              aria-label={detail}
              className="inline-flex items-center gap-1.5 font-bold text-danger-tint-ink underline-offset-2 hover:underline focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-danger"
            >
              <ShieldAlert className="h-4 w-4" aria-hidden="true" />
              {t("contract.flagged.label", { number })}
            </Link>
            <span className="text-danger-tint-ink/80">
              {t(`radar.report.who.types.${entity.entity_type}`)}:{" "}
              <span className="text-foreground">{name}</span>
            </span>
          </li>
        );
      })}
    </ul>
  );
}
