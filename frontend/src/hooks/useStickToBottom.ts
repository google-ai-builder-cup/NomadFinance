import { useCallback, useLayoutEffect, useRef, useState } from "react";

// Within this many pixels of the end counts as "reading the latest".
const NEAR_BOTTOM_PX = 48;

/**
 * Keeps a scrolling list showing its end while it grows (a reply streaming in), until the worker
 * scrolls up to read something. Then it leaves them where they are and offers a way back down.
 * `changeKey` is anything that changes when the content does. The jump is instant, never
 * animated: smooth scrolling on every token is jittery and ignores "reduce motion".
 */
export function useStickToBottom<T extends HTMLElement>(changeKey: unknown) {
  const ref = useRef<T>(null);
  const pinned = useRef(true);
  const [away, setAway] = useState(false);

  const toEnd = useCallback(() => {
    const element = ref.current;
    if (element !== null) {
      element.scrollTop = element.scrollHeight;
    }
  }, []);

  const onScroll = useCallback(() => {
    const element = ref.current;
    if (element === null) {
      return;
    }
    const gap = element.scrollHeight - element.scrollTop - element.clientHeight;
    pinned.current = gap <= NEAR_BOTTOM_PX;
    setAway(!pinned.current);
  }, []);

  /** Back to the latest message, and following it again. */
  const jumpToLatest = useCallback(() => {
    pinned.current = true;
    setAway(false);
    toEnd();
  }, [toEnd]);

  useLayoutEffect(() => {
    if (pinned.current) {
      toEnd();
    }
  }, [changeKey, toEnd]);

  // The list is shorter when the answer panel below it grows (a longer set of chips): the end
  // would slip out of view without any content changing.
  useLayoutEffect(() => {
    const element = ref.current;
    if (element === null || typeof ResizeObserver === "undefined") {
      return;
    }
    const observer = new ResizeObserver(() => {
      if (pinned.current) {
        toEnd();
      }
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [toEnd]);

  return { ref, onScroll, away, jumpToLatest };
}
