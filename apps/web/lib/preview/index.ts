/** Non-catalog preview inputs used until weather and calendar providers exist. */
export const previewWeather = [
  { date: "2026-09-22", condition: "Clear", high: 72 },
  { date: "2026-09-23", condition: "Rain", high: 64 },
  { date: "2026-09-24", condition: "Cloudy", high: 67 },
  { date: "2026-09-25", condition: "Clear", high: 70 },
  { date: "2026-09-26", condition: "Warm", high: 76 },
  { date: "2026-09-27", condition: "Breezy", high: 68 },
  { date: "2026-09-28", condition: "Cool", high: 61 },
] as const;

export const previewEvents = [
  { date: "2026-09-22", time: "09:00", title: "Studio review" },
  { date: "2026-09-25", time: "19:00", title: "Dinner" },
] as const;
