// 16 px text: a smaller size makes iOS zoom the page when the field takes focus. The border is the
// darker one the scam box uses, because the default field border is 1.3:1 against the card.
export const FIELD_CLASS =
  "min-h-11 w-full rounded-xl border border-muted-foreground/80 bg-card px-3 text-base shadow-sm " +
  "placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 " +
  "focus-visible:ring-ring aria-[invalid=true]:border-danger-ink";
