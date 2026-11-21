const DAY_KEY = "scentiq-bloom-day";

/** The local calendar day as YYYY-MM-DD. */
export function localDayKey(date: Date = new Date()): string {
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${date.getFullYear()}-${month}-${day}`;
}

/**
 * True the first time it is asked for a given day, so the Today bloom plays
 * once on first load. False afterwards, and false when storage is unavailable
 * (no bloom is better than one on every visit).
 */
export function claimDailyBloom(day: string): boolean {
  try {
    if (window.localStorage.getItem(DAY_KEY) === day) return false;
    window.localStorage.setItem(DAY_KEY, day);
    return true;
  } catch {
    return false;
  }
}
