import { apiClient } from "@/lib/server/api-client";
import { noticeCodeFor, parseProvider, settingsRedirect } from "@/lib/server/calendar-oauth";

/**
 * Where Google or Microsoft send the member back after consent.
 *
 * The code and state go to the service, which checks the state belongs to
 * this member, exchanges the code and stores the encrypted grant. This route
 * only redirects, so nothing from the provider is rendered.
 */
export async function GET(
  request: Request,
  context: { params: Promise<{ provider: string }> },
): Promise<Response> {
  const provider = parseProvider((await context.params).provider);
  const url = new URL(request.url);
  const code = url.searchParams.get("code");
  const state = url.searchParams.get("state");

  if (!provider) return settingsRedirect(request, "calendar_error", "authorization_failed");
  if (url.searchParams.get("error") === "access_denied") {
    return settingsRedirect(request, "calendar_error", "access_denied");
  }
  if (!code || !state) return settingsRedirect(request, "calendar_error", "authorization_failed");

  try {
    await apiClient.post(`/api/v1/calendar/connections/${provider}/callback`, { code, state });
  } catch (error) {
    return settingsRedirect(request, "calendar_error", noticeCodeFor(error));
  }
  return settingsRedirect(request, "calendar", "connected");
}
