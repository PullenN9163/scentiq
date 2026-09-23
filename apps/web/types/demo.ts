export type Season = "Spring" | "Summer" | "Fall" | "Winter";
export type Occasion = "Office" | "Casual" | "Date" | "Formal" | "Gym" | "Travel" | "Nightlife";
export type OwnershipType = "Bottle" | "Decant" | "Sample";

export interface DemoUser { id: string; name: string; initials: string; location: string; }
export interface FragranceNote { name: string; layer: "Top" | "Middle" | "Base"; }
export interface Fragrance {
  id: string; brand: string; name: string; concentration: string; description: string;
  family: string; accords: string[]; notes: FragranceNote[]; seasons: Season[];
  occasions: Occasion[]; longevity: string; projection: string; tone: string; demoPrice?: number;
}
export interface CollectionItem {
  id: string; fragranceId: string; ownershipType: OwnershipType; sizeMl: number;
  remainingMl: number; rating: number; purchasePrice: number; purchaseDate: string;
}
export interface WeatherDay { date: string; high: number; low: number; condition: string; humidity: number; }
export interface CalendarEvent {
  id: string; date: string; time: string; title: string; type: Occasion;
  setting: "Indoor" | "Outdoor" | "Mixed"; formality: "Relaxed" | "Smart" | "Formal";
}
export interface RecommendationCandidate { fragranceId: string; score: number; sprays: number; reason: string; }
export interface Recommendation {
  date: string; primary: RecommendationCandidate; alternatives: RecommendationCandidate[];
  reasons: string[]; warning?: string; status: "Planned" | "Accepted" | "Manual";
}
export interface WearLog { id: string; fragranceId: string; date: string; occasion: Occasion; sprays: number; }
export interface LayeringSuggestion {
  id: string; fragranceAId: string; fragranceBId: string; mode: "Safe" | "Contrast" | "Experimental";
  score: number; sharedNotes: string[]; complements: string[]; clashes: string[]; ratio: string;
  order: string; seasons: Season[]; occasions: Occasion[]; explanation: string;
}
export interface CollectionInsightSummary {
  totalOwned: number; totalCost: number; totalWears: number; mostWornId: string;
  leastWornId: string; highestRatedId: string; bestCostPerWearId: string;
  accordDistribution: { name: string; value: number }[];
  noteFrequency: { name: string; value: number }[];
  coverage: { name: Season | Occasion; score: number; label: "Weak" | "Moderate" | "Good" | "Excellent" }[];
}
