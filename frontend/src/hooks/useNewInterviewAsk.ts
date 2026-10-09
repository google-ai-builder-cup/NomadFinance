import { useState } from "react";

/**
 * Whether the worker has been asked "start over?" yet. The button and the question are two
 * pieces, because the button sits in a tight row (beside the step line) and the question needs a
 * row of its own. `returned` is true once the worker backed out: the button comes back and takes
 * focus, so a keyboard user is not sent to the top of the page.
 */
export function useNewInterviewAsk() {
  const [state, setState] = useState({ asking: false, returned: false });
  return {
    asking: state.asking,
    returned: state.returned,
    ask: () => setState({ asking: true, returned: false }),
    cancel: () => setState({ asking: false, returned: true }),
  };
}
