import type {
  CalendarEvent, CollectionInsightSummary, CollectionItem, DemoUser, Fragrance,
  LayeringSuggestion, Recommendation, WearLog, WeatherDay,
} from "@/types/demo";

export const demoUser: DemoUser = { id: "user-maya", name: "Maya Bennett", initials: "MB", location: "Brooklyn, NY" };

const note = (top: string, middle: string, base: string) => [
  { name: top, layer: "Top" as const }, { name: middle, layer: "Middle" as const }, { name: base, layer: "Base" as const },
];

export const fragrances: Fragrance[] = [
  { id: "cedar-after-rain", brand: "Atelier North", name: "Cedar After Rain", concentration: "Eau de Parfum", description: "Cool cedar, mineral air, and moss with a clean, calm trail.", family: "Woody", accords: ["cedar", "mineral", "moss"], notes: note("Bergamot", "Violet leaf", "Cedar"), seasons: ["Spring", "Fall"], occasions: ["Office", "Casual", "Travel"], longevity: "7 hours", projection: "Moderate", tone: "#5d7167", demoPrice: 145 },
  { id: "fig-circuit", brand: "Ninth House", name: "Fig Circuit", concentration: "Extrait", description: "Green fig and tea settle into polished sandalwood.", family: "Green", accords: ["fig", "green", "woody"], notes: note("Fig leaf", "Black tea", "Sandalwood"), seasons: ["Spring", "Summer", "Fall"], occasions: ["Office", "Casual", "Date"], longevity: "9 hours", projection: "Intimate", tone: "#697a46", demoPrice: 190 },
  { id: "amber-index", brand: "Maison Sillage", name: "Amber Index", concentration: "Eau de Parfum", description: "A measured amber with saffron warmth and dry vanilla.", family: "Amber", accords: ["amber", "spicy", "vanilla"], notes: note("Saffron", "Labdanum", "Vanilla"), seasons: ["Fall", "Winter"], occasions: ["Date", "Formal", "Nightlife"], longevity: "10 hours", projection: "Strong", tone: "#a76834", demoPrice: 175 },
  { id: "linen-neroli", brand: "Common Air", name: "Linen & Neroli", concentration: "Eau de Toilette", description: "Sunlit citrus, white linen, and soft musk.", family: "Citrus", accords: ["citrus", "clean", "musky"], notes: note("Neroli", "Orange blossom", "White musk"), seasons: ["Spring", "Summer"], occasions: ["Office", "Casual", "Gym", "Travel"], longevity: "5 hours", projection: "Soft", tone: "#d2b86d", demoPrice: 98 },
  { id: "violet-static", brand: "Parable", name: "Violet Static", concentration: "Eau de Parfum", description: "Powdered violet made electric with pink pepper and suede.", family: "Floral", accords: ["violet", "powdery", "leather"], notes: note("Pink pepper", "Violet", "Suede"), seasons: ["Spring", "Fall"], occasions: ["Date", "Formal", "Nightlife"], longevity: "8 hours", projection: "Moderate", tone: "#755b75", demoPrice: 160 },
  { id: "salt-library", brand: "Tide Archive", name: "Salt Library", concentration: "Eau de Parfum", description: "Sea salt, old paper, and driftwood in quiet balance.", family: "Aquatic", accords: ["marine", "woody", "mineral"], notes: note("Sea salt", "Paper", "Driftwood"), seasons: ["Spring", "Summer"], occasions: ["Casual", "Travel", "Office"], longevity: "6 hours", projection: "Moderate", tone: "#66808a", demoPrice: 132 },
  { id: "tobacco-velvet", brand: "Orison", name: "Tobacco Velvet", concentration: "Extrait", description: "Plum-dark tobacco wrapped in cacao and tonka.", family: "Tobacco", accords: ["tobacco", "sweet", "warm"], notes: note("Plum", "Tobacco", "Tonka"), seasons: ["Fall", "Winter"], occasions: ["Date", "Formal", "Nightlife"], longevity: "12 hours", projection: "Strong", tone: "#603b32", demoPrice: 220 },
  { id: "juniper-hour", brand: "Blue Hours", name: "Juniper Hour", concentration: "Eau de Parfum", description: "Crisp juniper, aromatic herbs, and transparent woods.", family: "Aromatic", accords: ["juniper", "aromatic", "fresh"], notes: note("Juniper", "Clary sage", "Blond woods"), seasons: ["Spring", "Summer", "Fall"], occasions: ["Office", "Casual", "Travel"], longevity: "7 hours", projection: "Moderate", tone: "#4e6d72", demoPrice: 138 },
  { id: "rose-ledger", brand: "Serein", name: "Rose Ledger", concentration: "Eau de Parfum", description: "Dry rose, ink, and patchouli with tailored precision.", family: "Floral", accords: ["rose", "earthy", "spicy"], notes: note("Cardamom", "Rose", "Patchouli"), seasons: ["Spring", "Fall", "Winter"], occasions: ["Office", "Date", "Formal"], longevity: "8 hours", projection: "Moderate", tone: "#985d62", demoPrice: 155 },
  { id: "solar-peel", brand: "Daymark", name: "Solar Peel", concentration: "Eau de Toilette", description: "Bitter orange and basil over sun-warmed vetiver.", family: "Citrus", accords: ["citrus", "green", "aromatic"], notes: note("Bitter orange", "Basil", "Vetiver"), seasons: ["Spring", "Summer"], occasions: ["Casual", "Gym", "Travel"], longevity: "5 hours", projection: "Fresh", tone: "#c88135", demoPrice: 88 },
  { id: "cashmere-code", brand: "Ninth House", name: "Cashmere Code", concentration: "Eau de Parfum", description: "Iris and cashmere woods with a close, velvety finish.", family: "Musky", accords: ["iris", "musky", "woody"], notes: note("Pear", "Iris", "Cashmere wood"), seasons: ["Fall", "Winter"], occasions: ["Office", "Date", "Formal"], longevity: "7 hours", projection: "Intimate", tone: "#8b8178", demoPrice: 168 },
  { id: "night-orchard", brand: "Common Air", name: "Night Orchard", concentration: "Eau de Parfum", description: "Black cherry, jasmine, and smoky resin after dark.", family: "Fruity", accords: ["cherry", "floral", "smoky"], notes: note("Black cherry", "Jasmine", "Benzoin"), seasons: ["Fall", "Winter"], occasions: ["Date", "Nightlife"], longevity: "9 hours", projection: "Strong", tone: "#623a4b", demoPrice: 150 },
  { id: "paper-musk", brand: "Atelier North", name: "Paper Musk", concentration: "Eau de Parfum", description: "Airy musk, rice paper, and pale woods.", family: "Musky", accords: ["musky", "clean", "woody"], notes: note("Aldehydes", "Rice paper", "Musk"), seasons: ["Spring", "Summer", "Fall"], occasions: ["Office", "Casual", "Travel"], longevity: "6 hours", projection: "Intimate", tone: "#b7afa1", demoPrice: 125 },
  { id: "leather-signal", brand: "Parable", name: "Leather Signal", concentration: "Extrait", description: "Sleek leather, black tea, and smoked birch.", family: "Leather", accords: ["leather", "smoky", "tea"], notes: note("Black tea", "Leather", "Birch"), seasons: ["Fall", "Winter"], occasions: ["Formal", "Nightlife"], longevity: "11 hours", projection: "Strong", tone: "#3f3a34", demoPrice: 205 },
  { id: "mint-condition", brand: "Daymark", name: "Mint Condition", concentration: "Eau de Cologne", description: "Spearmint and citrus over a sheer cedar base.", family: "Fresh", accords: ["mint", "citrus", "aromatic"], notes: note("Lime", "Spearmint", "Cedar"), seasons: ["Spring", "Summer"], occasions: ["Gym", "Casual", "Travel"], longevity: "4 hours", projection: "Fresh", tone: "#6f947d", demoPrice: 72 },
];

export const collection: CollectionItem[] = fragrances.slice(0, 12).map((fragrance, index) => ({ id: `owned-${index + 1}`, fragranceId: fragrance.id, ownershipType: index < 7 ? "Bottle" : index < 10 ? "Decant" : "Sample", sizeMl: index < 7 ? 100 : index < 10 ? 10 : 2, remainingMl: index < 7 ? 62 + index * 3 : index < 10 ? 6 : 1.4, rating: 3.6 + (index % 7) * 0.2, purchasePrice: 72 + index * 11, purchaseDate: `2026-${String((index % 7) + 1).padStart(2, "0")}-12` }));

export const weather: WeatherDay[] = [
  ["2026-09-22", 73, 61, "Clear after rain", 58], ["2026-09-23", 76, 64, "Sunny", 52], ["2026-09-24", 69, 58, "Light rain", 70], ["2026-09-25", 67, 55, "Cloudy", 63], ["2026-09-26", 72, 57, "Bright", 49], ["2026-09-27", 75, 62, "Warm", 55], ["2026-09-28", 65, 53, "Breezy", 46],
].map(([date, high, low, condition, humidity]) => ({ date: String(date), high: Number(high), low: Number(low), condition: String(condition), humidity: Number(humidity) }));

export const events: CalendarEvent[] = [
  ["event-1", "2026-09-22", "09:30", "Studio review", "Office", "Indoor", "Smart"], ["event-2", "2026-09-22", "19:00", "Dinner at Lilia", "Date", "Indoor", "Smart"], ["event-3", "2026-09-23", "12:00", "Prospect Park walk", "Casual", "Outdoor", "Relaxed"], ["event-4", "2026-09-24", "08:00", "Client presentation", "Office", "Indoor", "Formal"], ["event-5", "2026-09-24", "20:00", "Gallery opening", "Formal", "Indoor", "Smart"], ["event-6", "2026-09-25", "18:30", "Train to Hudson", "Travel", "Mixed", "Relaxed"], ["event-7", "2026-09-26", "14:00", "Bookshop afternoon", "Casual", "Indoor", "Relaxed"], ["event-8", "2026-09-27", "11:00", "Rooftop brunch", "Casual", "Outdoor", "Smart"], ["event-9", "2026-09-27", "21:00", "Live set", "Nightlife", "Indoor", "Smart"], ["event-10", "2026-09-28", "07:30", "Morning training", "Gym", "Indoor", "Relaxed"],
].map(([id, date, time, title, type, setting, formality]) => ({ id, date, time, title, type, setting, formality } as CalendarEvent));

const picks = ["cedar-after-rain", "fig-circuit", "rose-ledger", "salt-library", "juniper-hour", "linen-neroli", "paper-musk"];
export const recommendations: Recommendation[] = weather.map((day, index) => ({
  date: day.date,
  primary: { fragranceId: picks[index], score: 94 - index, sprays: index % 3 + 2, reason: "Balances the forecast, schedule, and your recent rotation." },
  alternatives: [
    { fragranceId: fragrances[(index + 3) % fragrances.length].id, score: 88 - index, sprays: 3, reason: "A brighter direction with similar occasion coverage." },
    { fragranceId: fragrances[(index + 7) % fragrances.length].id, score: 84 - index, sprays: 2, reason: "A quieter option that stays close to the skin." },
  ],
  reasons: [day.condition, "Fits your next event", "Not worn in the last five days"], warning: index === 2 ? "Apply lightly in close indoor settings." : undefined, status: "Planned",
}));

export const wearHistory: WearLog[] = Array.from({ length: 13 }, (_, index) => ({ id: `wear-${index + 1}`, fragranceId: fragrances[index % 9].id, date: `2026-09-${String(21 - index).padStart(2, "0")}`, occasion: fragrances[index % 9].occasions[0], sprays: 2 + (index % 3) }));

export const layeringSuggestions: LayeringSuggestion[] = [
  ["layer-1", "cedar-after-rain", "linen-neroli", "Safe", 91, ["citrus"], ["cedar", "musk"], [], "2:1", "Linen & Neroli first, Cedar After Rain second"],
  ["layer-2", "fig-circuit", "amber-index", "Contrast", 86, ["woody"], ["fig", "amber"], ["sweetness"], "1:1", "Fig Circuit first, Amber Index second"],
  ["layer-3", "rose-ledger", "paper-musk", "Safe", 89, ["clean"], ["rose", "musk"], [], "1:2", "Rose Ledger first, Paper Musk second"],
  ["layer-4", "salt-library", "tobacco-velvet", "Experimental", 78, ["woody"], ["salt", "tobacco"], ["density"], "2:1", "Tobacco Velvet first, Salt Library second"],
  ["layer-5", "juniper-hour", "violet-static", "Contrast", 83, ["aromatic"], ["juniper", "violet"], ["powder"], "2:1", "Violet Static first, Juniper Hour second"],
].map(([id, fragranceAId, fragranceBId, mode, score, sharedNotes, complements, clashes, ratio, order]) => ({ id, fragranceAId, fragranceBId, mode, score, sharedNotes, complements, clashes, ratio, order, seasons: ["Fall"], occasions: ["Date", "Casual"], explanation: "A deterministic demo pairing based on shared character and contrast. Treat it as guidance, not chemical certainty." } as LayeringSuggestion));

export const insights: CollectionInsightSummary = {
  totalOwned: collection.length, totalCost: collection.reduce((sum, item) => sum + item.purchasePrice, 0), totalWears: 47,
  mostWornId: "cedar-after-rain", leastWornId: "night-orchard", highestRatedId: "fig-circuit", bestCostPerWearId: "linen-neroli",
  accordDistribution: [{ name: "Woody", value: 28 }, { name: "Fresh", value: 22 }, { name: "Floral", value: 18 }, { name: "Amber", value: 15 }, { name: "Other", value: 17 }],
  noteFrequency: [{ name: "Cedar", value: 7 }, { name: "Musk", value: 6 }, { name: "Citrus", value: 6 }, { name: "Tea", value: 4 }, { name: "Amber", value: 3 }],
  coverage: ["Spring", "Summer", "Fall", "Winter", "Office", "Casual", "Date", "Formal", "Gym", "Travel", "Nightlife"].map((name, index) => ({ name, score: 42 + ((index * 13) % 55), label: index % 4 === 0 ? "Moderate" : index % 3 === 0 ? "Excellent" : "Good" })) as CollectionInsightSummary["coverage"],
};

export const getDemoFragranceById = (id: string) => fragrances.find((fragrance) => fragrance.id === id);
export const getDemoCollection = () => collection;
export const getDemoWeek = () => recommendations;
export const getDemoLayeringSuggestions = () => layeringSuggestions;
export const getDemoInsights = () => insights;
export const getDemoToday = () => ({ user: demoUser, weather: weather[0], events: events.filter((event) => event.date === weather[0].date), recommendation: recommendations[0], recentWears: wearHistory.slice(0, 3) });
