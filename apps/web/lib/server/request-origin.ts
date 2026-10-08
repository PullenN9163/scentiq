/** Validate browser mutations against the configured external application origin. */
export function hasApplicationOrigin(request: Request): boolean {
  const origin = request.headers.get("origin");
  if (!origin || origin === "null") return false;
  try {
    const configured = process.env.PUBLIC_APP_URL;
    if (!configured && process.env.NODE_ENV === "production") return false;
    return origin === new URL(configured || request.url).origin;
  } catch { return false; }
}
