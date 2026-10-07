import { useEffect, useRef } from "react";

/**
 * Puts keyboard focus on an element when it appears. For what takes the place of the control the
 * worker just used: a button that vanishes while it holds focus sends focus back to the top of the
 * page, so a keyboard user has to Tab through everything again and a screen reader says nothing
 * about what happened. The element needs `tabIndex={-1}`, so that script can focus it without it
 * joining the Tab order.
 */
export function useFocusOnMount<T extends HTMLElement>(enabled = true) {
  const ref = useRef<T>(null);
  useEffect(() => {
    if (enabled) {
      ref.current?.focus();
    }
  }, [enabled]);
  return ref;
}
