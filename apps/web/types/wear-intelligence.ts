import type { components } from "@/types/api.generated";

export type WearRecommendation = components["schemas"]["WearRecommendationResponse"] & { canonical_fragrance_id?: string | null; remaining_options?: number; options_exhausted?: boolean; generation_mode?: string; model_version?: string | null; profile_version?: string | null };
export type WearCandidate = components["schemas"]["WearRecommendationCandidate"];
export type WearPlan = components["schemas"]["WearRecommendationPlan"];
export type WearRequest = components["schemas"]["RecommendationWearRequest"];
export type WearFeedback = components["schemas"]["WearFeedbackResponse"];
export type WearFeedbackInput = components["schemas"]["WearFeedbackRequest"];
export type DecisionAction = components["schemas"]["RecommendationDecisionRequest"]["action"];
