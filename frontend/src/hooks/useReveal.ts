import { useEffect, useRef, useState } from "react";

/** True once the element has scrolled into view, then stays true. Without IntersectionObserver,
 * or when motion is reduced, it is true from the start so nothing is ever left hidden. */
export function useReveal<T extends Element>(rootMargin = "0px 0px -8% 0px") {
  const ref = useRef<T>(null);
  const [shown, setShown] = useState(
    () =>
      typeof IntersectionObserver === "undefined" ||
      (typeof window !== "undefined" &&
        window.matchMedia?.("(prefers-reduced-motion: reduce)").matches === true)
  );

  useEffect(() => {
    const el = ref.current;
    if (shown || !el) {
      return undefined;
    }
    const observer = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setShown(true);
          observer.disconnect();
        }
      },
      { rootMargin }
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [shown, rootMargin]);

  return [ref, shown] as const;
}
