// What to highlight in a checked message (NF-SA-016).
//
// The backend sends the message with its phone numbers, emails, ID and account numbers and links
// already replaced by tokens (`[PHONE]`, `[URL]`, ...), and the phrases that gave it away, each
// copied from that same text. This cuts the text into pieces for the screen: plain words,
// suspicious wording, and the tokens. Pure, so every edge case is testable without a screen.

export const TOKENS = ["PHONE", "EMAIL", "ID", "ACCOUNT", "URL"] as const;
export type MaskToken = (typeof TOKENS)[number];

export interface MessagePiece {
  text: string;
  /** Part of a phrase that gave the message away. */
  highlighted: boolean;
  /** Set when this piece is one of the redaction tokens. */
  token: MaskToken | null;
}

const TOKEN_PATTERN = new RegExp(`\\[(${TOKENS.join("|")})\\]`, "g");

function escapeForRegExp(text: string): string {
  return text.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

type Range = readonly [start: number, end: number];

/** Where each phrase occurs in `text`, ignoring case, with overlapping and touching ranges
 * merged so "pay the fee" and "the fee today" read as one highlight. */
function phraseRanges(text: string, phrases: readonly string[]): Range[] {
  const found: Range[] = [];
  for (const phrase of phrases) {
    const wanted = phrase.trim();
    if (wanted === "") {
      continue;
    }
    // A regular expression rather than `indexOf` on a lower-cased copy: lower-casing can change
    // a text's length in some scripts, which would shift every position after it.
    for (const match of text.matchAll(new RegExp(escapeForRegExp(wanted), "giu"))) {
      found.push([match.index, match.index + match[0].length]);
    }
  }
  found.sort((a, b) => a[0] - b[0]);
  const merged: [number, number][] = [];
  for (const [start, end] of found) {
    const last = merged[merged.length - 1];
    if (last && start <= last[1]) {
      last[1] = Math.max(last[1], end);
    } else {
      merged.push([start, end]);
    }
  }
  return merged;
}

/** The message as pieces to render, in order, covering every character exactly once. */
export function splitMessage(text: string, phrases: readonly string[]): MessagePiece[] {
  if (text === "") {
    return [];
  }
  const highlights = phraseRanges(text, phrases);
  const tokens = [...text.matchAll(TOKEN_PATTERN)].map((match) => ({
    start: match.index,
    end: match.index + match[0].length,
    name: match[1] as MaskToken,
  }));

  // Every place a piece can start or end: the text's edges, each highlight's and each token's.
  const cuts = new Set<number>([0, text.length]);
  for (const [start, end] of highlights) {
    cuts.add(start);
    cuts.add(end);
  }
  for (const token of tokens) {
    cuts.add(token.start);
    cuts.add(token.end);
  }
  const edges = [...cuts].sort((a, b) => a - b);

  const pieces: MessagePiece[] = [];
  for (let i = 0; i < edges.length - 1; i += 1) {
    const [from, to] = [edges[i], edges[i + 1]];
    const token = tokens.find((candidate) => candidate.start === from && candidate.end === to);
    pieces.push({
      text: text.slice(from, to),
      highlighted: highlights.some(([start, end]) => from >= start && to <= end),
      token: token?.name ?? null,
    });
  }
  return pieces;
}
