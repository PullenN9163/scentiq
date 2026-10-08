import { describe, expect, it } from "vitest";
import { readAgentStream } from "./stream";

function stream(chunks: Uint8Array[]) {
  return new ReadableStream<Uint8Array>({ start(controller) { chunks.forEach((chunk) => controller.enqueue(chunk)); controller.close(); } });
}

describe("Agent NDJSON reader", () => {
  it("preserves split lines and multibyte text across transport chunks", async () => {
    const bytes = new TextEncoder().encode('{"type":"text_delta","delta":"fresher 🌿"}\n{"type":"done"}\n');
    const events = [];
    for await (const event of readAgentStream(stream(Array.from(bytes, (byte) => new Uint8Array([byte]))))) events.push(event);
    expect(events).toEqual([{ type: "text_delta", delta: "fresher 🌿" }, { type: "done" }]);
  });
  it("rejects malformed, unknown, and incomplete streams", async () => {
    for (const text of ['{"type":"secret","token":"x"}\n', '{"type":"text_delta"}\n', '{"type":"text_delta","delta":"partial"}\n', 'bad\n']) {
      const consume = async () => { for await (const event of readAgentStream(stream([new TextEncoder().encode(text)]))) void event; };
      await expect(consume()).rejects.toThrow();
    }
  });
});
