import {
  BadgeAlert,
  Clock,
  Gift,
  Hourglass,
  ShieldAlert,
  Users,
  type LucideIcon,
} from "lucide-react";
import { useId, useState } from "react";

import { useI18n } from "@/hooks/useI18n";
import { cn } from "@/lib/utils";

const ICONS: Readonly<Record<string, LucideIcon>> = {
  urgency: Clock,
  authority: BadgeAlert,
  scarcity: Hourglass,
  fear: ShieldAlert,
  reciprocity: Gift,
  social_proof: Users,
};

export interface TacticChipsProps {
  /** Taxonomy tactic ids, the strongest first. */
  tactics: readonly string[];
  /** The explainer's own words for each tactic of this message, when it was written. */
  explanations?: readonly { tactic: string; text: string }[];
}

/** The tricks a message uses, each a button that opens a plain explanation. The explainer's text
 * is used when there is one; otherwise a short general line, so a tap always answers. One is open
 * at a time, announced to a screen reader through `aria-expanded`. */
export default function TacticChips({ tactics, explanations = [] }: TacticChipsProps) {
  const { t } = useI18n("scam");
  const panelId = useId();
  const [openTactic, setOpenTactic] = useState<string | null>(null);

  if (tactics.length === 0) {
    return null;
  }

  const label = (tactic: string) =>
    t(`result.tactic.${tactic}.label`, { defaultValue: tactic.replaceAll("_", " ") });
  const explanation = (tactic: string) =>
    explanations.find((item) => item.tactic === tactic)?.text ??
    t(`result.tactic.${tactic}.what`, { defaultValue: "" });

  return (
    <div className="space-y-3">
      <ul className="flex flex-wrap gap-2">
        {tactics.map((tactic) => {
          const Icon = ICONS[tactic] ?? BadgeAlert;
          const open = openTactic === tactic;
          return (
            <li key={tactic}>
              <button
                type="button"
                aria-expanded={open}
                aria-controls={open ? panelId : undefined}
                onClick={() => setOpenTactic(open ? null : tactic)}
                className={cn(
                  "inline-flex min-h-11 items-center gap-2 rounded-full border px-3.5 text-sm font-semibold",
                  "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
                  open
                    ? "border-radar bg-radar-tint text-radar-ink"
                    : "border-input bg-card hover:bg-accent"
                )}
              >
                <Icon className="h-4 w-4 shrink-0" aria-hidden="true" />
                {label(tactic)}
              </button>
            </li>
          );
        })}
      </ul>
      {openTactic !== null && (
        <div id={panelId} className="rounded-xl bg-muted/60 p-3 text-sm leading-6">
          <p className="font-bold">{label(openTactic)}</p>
          <p>{explanation(openTactic)}</p>
        </div>
      )}
    </div>
  );
}
