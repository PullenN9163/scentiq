import { Webhook } from "svix";

/**
 * Clerk's signed identity-event webhook.
 *
 * This route is public because Clerk authenticates with a Svix signature rather
 * than a session. The signature is verified here, the event normalised, and
 * only then forwarded to the internal FastAPI endpoint with a dedicated service
 * credential. FastAPI never sees the provider signature, and this route never
 * touches the database.
 */

type ClerkEvent = {
  type: string;
  data?: { id?: unknown };
};

function serviceConfiguration():
  | { baseUrl: string; serviceToken: string; webhookSecret: string }
  | null {
  const baseUrl = process.env.API_INTERNAL_URL;
  const serviceToken = process.env.INTERNAL_SERVICE_TOKEN;
  const webhookSecret = process.env.CLERK_WEBHOOK_SECRET;
  if (!baseUrl || !serviceToken || !webhookSecret) {
    return null;
  }
  return { baseUrl: baseUrl.replace(/\/+$/, ""), serviceToken, webhookSecret };
}

export async function POST(request: Request): Promise<Response> {
  const configuration = serviceConfiguration();
  if (!configuration) {
    // Fail closed: an unconfigured deployment must not silently accept events.
    console.error("clerk_webhook_not_configured");
    return Response.json({ code: "not_configured" }, { status: 503 });
  }

  const payload = await request.text();
  const svixId = request.headers.get("svix-id");
  const svixTimestamp = request.headers.get("svix-timestamp");
  const svixSignature = request.headers.get("svix-signature");
  if (!svixId || !svixTimestamp || !svixSignature) {
    return Response.json({ code: "missing_signature" }, { status: 400 });
  }

  let event: ClerkEvent;
  try {
    event = new Webhook(configuration.webhookSecret).verify(payload, {
      "svix-id": svixId,
      "svix-timestamp": svixTimestamp,
      "svix-signature": svixSignature,
    }) as ClerkEvent;
  } catch {
    // The body is never logged; it is unverified input.
    console.warn("clerk_webhook_signature_rejected");
    return Response.json({ code: "invalid_signature" }, { status: 400 });
  }

  if (event.type !== "user.deleted") {
    // Acknowledged and ignored, so Clerk does not retry events we do not act on.
    return Response.json({ ignored: event.type }, { status: 200 });
  }

  const subject = typeof event.data?.id === "string" ? event.data.id : null;
  if (!subject) {
    return Response.json({ code: "missing_subject" }, { status: 400 });
  }

  let response: Response;
  try {
    response = await fetch(`${configuration.baseUrl}/api/v1/internal/identity-events`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "x-scentiq-service-token": configuration.serviceToken,
      },
      // `svix-id` is the provider's event id, which makes replays no-ops.
      body: JSON.stringify({
        event_id: svixId,
        event_type: "user.deleted",
        subject,
      }),
      cache: "no-store",
      signal: AbortSignal.timeout(10_000),
    });
  } catch {
    console.error("clerk_webhook_forward_unreachable");
    // 500 so Clerk retries; processing is idempotent, so a retry is safe.
    return Response.json({ code: "service_unreachable" }, { status: 500 });
  }

  if (!response.ok) {
    console.error("clerk_webhook_forward_failed", { status: response.status });
    return Response.json({ code: "forward_failed" }, { status: 500 });
  }

  return Response.json({ received: true }, { status: 200 });
}
