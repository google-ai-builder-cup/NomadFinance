import { cn } from "@/lib/utils";

export interface QuickReply {
  id: string;
  /** Already translated. */
  label: string;
}

export interface QuickReplyChipsProps {
  options: readonly QuickReply[];
  onSelect: (option: QuickReply) => void;
  /** Accessible name of the group, e.g. "Suggested answers". */
  groupLabel: string;
  /** Set to mark one chip as chosen (`aria-pressed`). Leave unset for one-shot replies. */
  selectedId?: string | null;
  disabled?: boolean;
  className?: string;
}

/** Tappable suggested answers under a chat message. Plain buttons, so Tab, Enter and Space work
 * with no extra code, and each one is at least 44 px tall for a thumb. */
export default function QuickReplyChips({
  options,
  onSelect,
  groupLabel,
  selectedId,
  disabled = false,
  className,
}: QuickReplyChipsProps) {
  return (
    <div role="group" aria-label={groupLabel} className={cn("flex flex-wrap gap-2", className)}>
      {options.map((option) => {
        const selected = selectedId === option.id;
        return (
          <button
            key={option.id}
            type="button"
            disabled={disabled}
            aria-pressed={selectedId === undefined ? undefined : selected}
            onClick={() => onSelect(option)}
            className={cn(
              "min-h-11 rounded-full border px-4 py-2 text-sm font-semibold transition-colors",
              "disabled:pointer-events-none disabled:opacity-50",
              selected
                ? "border-primary bg-primary text-primary-foreground"
                : "border-input bg-card text-foreground hover:bg-accent"
            )}
          >
            {option.label}
          </button>
        );
      })}
    </div>
  );
}
