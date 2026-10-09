export interface SseFrame {
  /** The `event:` name; `message` when the frame has none, as the format says. */
  event: string;
  /** The `data:` lines joined with a newline. */
  data: string;
}

export interface SseParser {
  /** Feed the next piece of text; returns the frames it completed. */
  push(chunk: string): SseFrame[];
}

// A blank line ends a frame. Servers may write \n, \r\n or a lone \r.
const FRAME_END = /\r\n\r\n|\n\n|\r\r/;

function parseFrame(block: string): SseFrame | null {
  let event = "message";
  const data: string[] = [];
  for (const line of block.split(/\r\n|\n|\r/)) {
    // A line that starts with ":" is a comment; the server's heartbeat is one (`: ping`).
    if (line === "" || line.startsWith(":")) {
      continue;
    }
    const colon = line.indexOf(":");
    const field = colon === -1 ? line : line.slice(0, colon);
    // One space after the colon belongs to the format, not to the value.
    const value = colon === -1 ? "" : line.slice(colon + 1).replace(/^ /, "");
    if (field === "event") {
      event = value;
    } else if (field === "data") {
      data.push(value);
    }
  }
  return data.length === 0 ? null : { event, data: data.join("\n") };
}

/**
 * Splits a text stream into Server-Sent Events frames. A network chunk can end in the middle of a
 * frame, so the unfinished part is kept until the next chunk completes it. A frame the stream
 * never finished (the connection dropped) is never returned: half a message is not a message.
 */
export function createSseParser(): SseParser {
  let buffer = "";
  return {
    push(chunk) {
      buffer += chunk;
      const frames: SseFrame[] = [];
      for (let end = FRAME_END.exec(buffer); end !== null; end = FRAME_END.exec(buffer)) {
        const frame = parseFrame(buffer.slice(0, end.index));
        buffer = buffer.slice(end.index + end[0].length);
        if (frame !== null) {
          frames.push(frame);
        }
      }
      return frames;
    },
  };
}
