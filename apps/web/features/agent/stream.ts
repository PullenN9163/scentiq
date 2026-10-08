export type AgentCard = {
  kind: "recommendation" | "week" | "collection" | "insights" | "wears" | "discover" | "layering" | "fragrance";
  data: unknown;
};
export type AgentEvent =
  | { type: "status" | "tool_started" | "tool_finished" | "fallback"; label?: string; tool?: string }
  | { type: "text_delta"; delta: string }
  | { type: "card"; card: AgentCard }
  | { type: "done" };

const kinds = new Set(["recommendation", "week", "collection", "insights", "wears", "discover", "layering", "fragrance"]);

function parse(line: string): AgentEvent {
  const value: unknown = JSON.parse(line);
  if (!value || typeof value !== "object" || !("type" in value)) throw new Error("Invalid advisor event");
  const type = value.type;
  if (type === "done") return { type };
  if (type === "text_delta" && "delta" in value && typeof value.delta === "string") return { type, delta: value.delta };
  if (type === "card" && "card" in value && value.card && typeof value.card === "object" && "kind" in value.card && "data" in value.card && typeof value.card.kind === "string" && kinds.has(value.card.kind)) return { type, card: value.card as AgentCard };
  if (type === "status" || type === "tool_started" || type === "tool_finished" || type === "fallback") {
    return { type, label: "label" in value && typeof value.label === "string" ? value.label : undefined };
  }
  throw new Error("Invalid advisor event");
}

/** Incremental UTF-8 NDJSON, bounded against malformed or incomplete upstreams. */
export async function* readAgentStream(stream: ReadableStream<Uint8Array>): AsyncGenerator<AgentEvent> {
  const reader = stream.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  let completed = false;
  let bytesRead = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (value) {
        bytesRead += value.byteLength;
        if (bytesRead > 1_000_000) throw new Error("Advisor response exceeded its limit");
      }
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      if (buffer.length > 100_000) throw new Error("Advisor event exceeded its limit");
      let newline: number;
      while ((newline = buffer.indexOf("\n")) >= 0) {
        const line = buffer.slice(0, newline).trim();
        buffer = buffer.slice(newline + 1);
        if (!line) continue;
        const event = parse(line);
        yield event;
        if (event.type === "done") { completed = true; return; }
      }
      if (done) {
        if (buffer.trim()) {
          const event = parse(buffer);
          yield event;
          completed = event.type === "done";
        }
        if (!completed) throw new Error("Advisor response was interrupted. Please try again.");
        return;
      }
    }
  } finally {
    await reader.cancel().catch(() => undefined);
    reader.releaseLock();
  }
}
