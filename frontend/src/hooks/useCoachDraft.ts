import {
  createContext,
  createElement,
  useCallback,
  useContext,
  useState,
  type ReactElement,
  type ReactNode,
} from "react";

import { readDraft, writeDraft, type DraftFields } from "@/utils/coachDraft";

/** Whose draft, in which interview, for which question. */
export interface DraftScope {
  uid: string;
  sessionId: string;
  /** The question being asked: `stage:slot`. A new question has its own (empty) draft. */
  question: string;
}

const DraftContext = createContext<DraftScope | null>(null);

export interface CoachDraftProviderProps {
  scope: DraftScope;
  children: ReactNode;
}

/** Keeps what the helpers below it hold, so a reload does not lose it. Without one the helpers
 * behave as plain state (tests, and any screen that has no signed-in person to key a draft by). */
export function CoachDraftProvider({ scope, children }: CoachDraftProviderProps): ReactElement {
  return createElement(DraftContext.Provider, { value: scope }, children);
}

const prefixed = (namespace: string, fields: DraftFields): DraftFields =>
  Object.fromEntries(
    Object.entries(fields).map(([name, value]) => [`${namespace}.${name}`, value])
  );

function load<T extends DraftFields>(scope: DraftScope | null, namespace: string, initial: T): T {
  if (scope === null) {
    return initial;
  }
  const kept = readDraft(scope.uid, scope.sessionId, scope.question);
  const fields: DraftFields = { ...initial };
  for (const name of Object.keys(initial)) {
    const value = kept[`${namespace}.${name}`];
    if (value !== undefined) {
      fields[name] = value;
    }
  }
  return fields as T;
}

/**
 * The text fields of one helper (the answer box, an amount, a date), kept as a draft while the
 * question stays the same. Returns the fields and a function that changes some of them. All fields
 * are strings; an empty one means "nothing typed", so the draft of an untouched helper is empty.
 * `resetKey` starts the fields afresh whenever it changes, with or without a draft to key by.
 */
export function useDraftFields<T extends DraftFields>(
  namespace: string,
  initial: T,
  resetKey = ""
): [T, (patch: Partial<T>) => void] {
  const scope = useContext(DraftContext);
  const key = `${scope === null ? "" : `${scope.uid}|${scope.sessionId}|${scope.question}`}|${resetKey}`;
  const [held, setHeld] = useState(() => ({ key, fields: load(scope, namespace, initial) }));

  let fields = held.fields;
  if (held.key !== key) {
    // The question changed: this helper starts from that question's draft, usually none.
    fields = load(scope, namespace, initial);
    setHeld({ key, fields });
  }

  const change = useCallback(
    (patch: Partial<T>) => {
      const next = { ...fields, ...patch } as T;
      setHeld({ key, fields: next });
      if (scope !== null) {
        writeDraft(scope.uid, scope.sessionId, scope.question, prefixed(namespace, next));
      }
    },
    [fields, key, namespace, scope]
  );

  return [fields, change];
}
