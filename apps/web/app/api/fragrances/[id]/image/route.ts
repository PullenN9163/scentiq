import { hasApplicationOrigin } from "@/lib/server/request-origin";
import { auth } from "@clerk/nextjs/server";
import { revalidatePath } from "next/cache";

const MAX_BYTES = 5 * 1024 * 1024;
type Context = { params: Promise<{ id: string }> };
async function proxyImage(request: Request, context: Context): Promise<Response> {
  const { id } = await context.params;
  if (!/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(id)) return Response.json({ message: "Image not found." }, { status: 404 });
  const token = await (await auth()).getToken();
  if (!token) return Response.json({ message: "Sign in to continue." }, { status: 401 });
  if (request.method !== "GET" && !hasApplicationOrigin(request)) return Response.json({ message: "Invalid request origin." }, { status: 403 });
  const base = process.env.API_INTERNAL_URL || (process.env.NODE_ENV === "development" ? "http://localhost:8000" : "");
  if (!base) return Response.json({ message: "Image storage is unavailable." }, { status: 503 });
  const headers: Record<string, string> = { Authorization: `Bearer ${token}` };
  let body: Uint8Array | undefined;
  if (request.method === "PUT") {
    const mime = request.headers.get("content-type")?.split(";")[0] ?? "";
    if (!["image/jpeg", "image/png", "image/webp"].includes(mime)) return Response.json({ message: "Choose a JPEG, PNG, or WebP image." }, { status: 422 });
    const chunks: Uint8Array[] = [];
    let length = 0;
    const reader = request.body?.getReader();
    if (!reader) return Response.json({ message: "Choose an image." }, { status: 422 });
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      length += value.byteLength;
      if (length > MAX_BYTES) { await reader.cancel(); return Response.json({ message: "Images must be 5 MB or smaller." }, { status: 413 }); }
      chunks.push(value);
    }
    body = new Uint8Array(length);
    let offset = 0;
    for (const chunk of chunks) { body.set(chunk, offset); offset += chunk.length; }
    headers["Content-Type"] = mime;
  }
  try {
    const result = await fetch(`${base.replace(/\/+$/, "")}/api/v1/fragrances/${id}/image`, { method: request.method, headers, body: body as BodyInit | undefined, cache: "no-store", signal: AbortSignal.timeout(20_000) });
    if (result.ok && request.method !== "GET") { revalidatePath("/collection"); revalidatePath(`/collection/${id}`); }
    return new Response(result.status === 204 ? null : result.body, { status: result.status, headers: { "Content-Type": result.headers.get("content-type") ?? "application/json", "Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff" } });
  } catch { return Response.json({ message: "Image storage could not be reached. Try again." }, { status: 503 }); }
}
export const GET = proxyImage;
export const PUT = proxyImage;
export const DELETE = proxyImage;
