export type ApiAvailability = "available" | "unavailable";

export async function getApiAvailability(
  fetcher: typeof fetch = fetch,
  baseUrl = "",
): Promise<ApiAvailability> {
  const normalizedBaseUrl = baseUrl.replace(/\/+$/, "");
  if (!normalizedBaseUrl) {
    return "unavailable";
  }

  try {
    const response = await fetcher(`${normalizedBaseUrl}/health/live`, {
      cache: "no-store",
      signal: AbortSignal.timeout(3000),
    });

    return response.ok ? "available" : "unavailable";
  } catch {
    return "unavailable";
  }
}
