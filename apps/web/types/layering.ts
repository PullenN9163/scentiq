import type { components } from "@/types/api.generated";

type Schemas = components["schemas"];
export type StackMode = Schemas["LayeringStackSuggestion"]["mode"];
export type LayeringGoal = NonNullable<Schemas["LayeringStackSuggestion"]["goal"]>;
export type LayeringStackSuggestion = Schemas["LayeringStackSuggestion"];
export type SavedLayeringStack = Schemas["SavedLayeringStack"];
export type LayeringStackWear = Schemas["LayeringStackWearResponse"];
export type LayeringIntelligencePage = Schemas["LayeringIntelligencePage"];
