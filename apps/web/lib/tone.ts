/**
 * A stable colour for a fragrance's card art.
 *
 * The demo data carried a hand-picked `tone` per fragrance; the API does not
 * store presentation colours. Deriving one from the id keeps the existing look
 * while guaranteeing the same fragrance always renders the same colour.
 */

// Drawn from the palette the demo cards already used.
const TONES = [
  "#5d7167",
  "#697a46",
  "#a76834",
  "#d2b86d",
  "#755b75",
  "#66808a",
  "#603b32",
  "#4e6d72",
  "#985d62",
  "#c88135",
  "#8b8178",
  "#623a4b",
  "#b7afa1",
  "#3f3a34",
  "#6f947d",
] as const;

export function toneFor(id: string): string {
  let hash = 0;
  for (let index = 0; index < id.length; index += 1) {
    // Simple deterministic string hash; no cryptographic purpose.
    hash = (hash * 31 + id.charCodeAt(index)) % 2 ** 31;
  }
  return TONES[hash % TONES.length];
}
