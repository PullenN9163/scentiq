import { apiClient } from "@/lib/server/api-client";
import { noticeCodeFor, parseProvider, settingsRedirect } from "@/lib/server/calendar-oauth";

/**
 * Starts a calendar connection: asks the service for the provider consent URL
 * (which records a single-use state and PKCE verifier) and sends the browser
 * there. Protected by the session like the rest of the app.
 */
export async function GET(
  request: Request,
  context: { params: Promise<{ provider: string }> },
): Promise<Response> {
  const provider = parseProvider((await context.params).provider);
  if (!provider) return settingsRedirect(request, "calendar_error", "authorization_failed");

  try {
    const { authorization_url } = await apiClient.post<{ authorization_url: string }>(
      `/api/v1/calendar/connections/${provider}/authorize`,
    );
    return Response.redirect(authorization_url, 303);
  } catch (error) {
    return settingsRedirect(request, "calendar_error", noticeCodeFor(error));
  }
}
