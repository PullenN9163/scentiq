import { hasApplicationOrigin } from "@/lib/server/request-origin";
import { apiClient, ApiError } from "@/lib/server/api-client";

export const runtime = "nodejs";
export const dynamic = "force-dynamic";

export async function POST(request: Request): Promise<Response> {
  if (!hasApplicationOrigin(request)) return Response.json({message:"Invalid request origin."},{status:403});
  try {
    // Bound actual bytes, including requests without Content-Length.
    if (!request.body) return Response.json({ message: "Enter a question." }, { status: 400 });
    const reader = request.body.getReader();
    const decoder = new TextDecoder();
    let size = 0;
    let raw = "";
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        size += value.byteLength;
        if (size > 65536) { await reader.cancel(); return Response.json({ message: "Conversation is too long." }, { status: 413 }); }
        raw += decoder.decode(value, { stream: true });
      }
      raw += decoder.decode();
    } finally { reader.releaseLock(); }
    let body: unknown;
    try { body = JSON.parse(raw); } catch { return Response.json({ message: "Invalid advisor request." }, { status: 400 }); }
    const upstream = await apiClient.stream("/api/v1/agent/chat", body, AbortSignal.any([request.signal, AbortSignal.timeout(30000)]));
    if (!upstream.body) return Response.json({ message: "The advisor is unavailable." }, { status: 503 });
    return new Response(upstream.body, { headers: { "Content-Type": "application/x-ndjson", "Cache-Control": "no-store", "X-Accel-Buffering": "no" } });
  } catch (error) {
    if (error instanceof ApiError) return Response.json({ message: error.message, code: error.code }, { status: error.status });
    return Response.json({ message: "The advisor is unavailable. Try again." }, { status: 503 });
  }
}
