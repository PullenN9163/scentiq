/**
 * Whether the Atelier interface is on. Off unless the variable is "true"
 * (any case). Bracket notation keeps this a runtime lookup in the standalone
 * server, so operators can switch it with configuration rather than a build.
 */
export function isAtelierEnabled(): boolean {
  return process.env["SCENTIQ_ATELIER_UI_ENABLED"]?.toLowerCase() === "true";
}
