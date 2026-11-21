/** "Reduce effects": a per-browser setting kept in a cookie, read before paint. */
export const EFFECTS_COOKIE = "scentiq-effects";

export function effectsReducedFromCookie(value: string | undefined): boolean {
  return value === "reduced";
}

/** Writes the cookie and the root attribute; the server layout reads the cookie on the next render. */
export function setReduceEffects(reduced: boolean) {
  const secure = location.protocol === "https:" ? "; Secure" : "";
  document.cookie = reduced
    ? `${EFFECTS_COOKIE}=reduced; Path=/; Max-Age=31536000; SameSite=Lax${secure}`
    : `${EFFECTS_COOKIE}=; Path=/; Max-Age=0; SameSite=Lax${secure}`;
  if (reduced) document.documentElement.dataset.effects = "reduced";
  else delete document.documentElement.dataset.effects;
}

export function readReduceEffects(): boolean {
  if (typeof document === "undefined") return false;
  return document.documentElement.dataset.effects === "reduced";
}
