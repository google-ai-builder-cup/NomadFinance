import { describe, expect, it } from "vitest";

import { createSseParser } from "@/utils/sse";

describe("createSseParser", () => {
  it("returns a frame once its blank line has arrived, with the event name and data", () => {
    const parser = createSseParser();

    const frames = parser.push('event: token\ndata: {"text":"Hi"}\n\n');

    expect(frames).toEqual([{ event: "token", data: '{"text":"Hi"}' }]);
  });

  it("keeps half a frame until the next chunk completes it, wherever the chunk ends", () => {
    const parser = createSseParser();
    const whole = 'event: token\ndata: {"text":"Hello"}\n\nevent: done\ndata: {"ok":true}\n\n';

    // Every possible split point, including the middle of a word and between the two newlines.
    for (let cut = 1; cut < whole.length; cut += 1) {
      const split = createSseParser();
      const frames = [...split.push(whole.slice(0, cut)), ...split.push(whole.slice(cut))];
      expect(frames.map((frame) => frame.event)).toEqual(["token", "done"]);
    }
    expect(parser.push("event: token\ndata: {").length).toBe(0);
  });

  it("ignores the heartbeat comment, alone or inside a frame", () => {
    const parser = createSseParser();

    expect(parser.push(": ping\n\n")).toEqual([]);
    expect(parser.push(": ping\nevent: token\ndata: 1\n\n")).toEqual([
      { event: "token", data: "1" },
    ]);
  });

  it("reads CRLF line ends", () => {
    const parser = createSseParser();

    expect(parser.push("event: done\r\ndata: 2\r\n\r\n")).toEqual([{ event: "done", data: "2" }]);
  });

  it("joins several data lines with a newline and calls an unnamed event `message`", () => {
    const parser = createSseParser();

    expect(parser.push("data: a\ndata: b\n\n")).toEqual([{ event: "message", data: "a\nb" }]);
  });

  it("strips one space after the colon and no more", () => {
    const parser = createSseParser();

    expect(parser.push("data:  two\n\n")).toEqual([{ event: "message", data: " two" }]);
    expect(parser.push("data:none\n\n")).toEqual([{ event: "message", data: "none" }]);
  });

  it("keeps the Hindi text of a frame whole", () => {
    const parser = createSseParser();

    const [frame] = parser.push('event: token\ndata: {"text":"कर्ज़ बाकी है"}\n\n');

    expect(JSON.parse(frame.data)).toEqual({ text: "कर्ज़ बाकी है" });
  });

  it("never returns a frame the stream did not finish", () => {
    const parser = createSseParser();

    expect(parser.push('event: token\ndata: {"text":"What kind of"}')).toEqual([]);
  });
});
