import { getApiAvailability } from "@/lib/api-status";

export async function GET(): Promise<Response> {
  const developmentDefault =
    process.env.NODE_ENV === "development" ? "http://localhost:8000" : undefined;
  const baseUrl = process.env.API_INTERNAL_URL || developmentDefault;
  const api = await getApiAvailability(fetch, baseUrl);

  return Response.json({ api });
}
