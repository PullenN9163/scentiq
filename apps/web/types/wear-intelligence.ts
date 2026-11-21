import type { components } from "@/types/api.generated";

export type WearRecommendation = components["schemas"]["WearRecommendationResponse"];
export type WearCandidate = components["schemas"]["WearRecommendationCandidate"];
export type WearPlan = components["schemas"]["WearRecommendationPlan"];
// blend_key defaults to "" on the server, so callers may omit it.
export type WearRequest = Omit<components["schemas"]["RecommendationWearRequest"], "blend_key"> & { blend_key?: string };
export type WearFeedback = components["schemas"]["WearFeedbackResponse"];
export type WearFeedbackInput = components["schemas"]["WearFeedbackRequest"];
export type DecisionAction = components["schemas"]["RecommendationDecisionRequest"]["action"];
