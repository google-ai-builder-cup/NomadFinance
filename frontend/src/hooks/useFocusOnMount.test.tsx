// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useFocusOnMount } from "@/hooks/useFocusOnMount";

afterEach(cleanup);

function Result({ enabled }: { enabled?: boolean }) {
  const ref = useFocusOnMount<HTMLParagraphElement>(enabled);
  return (
    <p ref={ref} tabIndex={-1}>
      The answer
    </p>
  );
}

describe("useFocusOnMount", () => {
  it("puts focus on the element when it appears", () => {
    render(<Result />);

    expect(document.activeElement).toBe(screen.getByText("The answer"));
  });

  it("leaves focus alone when told not to, as for a stored check opened from a list", () => {
    render(<Result enabled={false} />);

    expect(document.activeElement).toBe(document.body);
  });

  it("takes focus when it is switched on later", () => {
    const { rerender } = render(<Result enabled={false} />);

    rerender(<Result enabled />);

    expect(document.activeElement).toBe(screen.getByText("The answer"));
  });

  it("does not put the element in the Tab order", () => {
    render(<Result />);

    expect(screen.getByText("The answer").tabIndex).toBe(-1);
  });
});
