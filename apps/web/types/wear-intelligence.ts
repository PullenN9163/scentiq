import type { components } from "@/types/api.generated";

export type WearRecommendation = components["schemas"]["WearRecommendationResponse"];
export type WearCandidate = components["schemas"]["WearRecommendationCandidate"];
export type WearPlan = components["schemas"]["WearRecommendationPlan"];
export type WearRequest = components["schemas"]["RecommendationWearRequest"];
export type WearFeedback = components["schemas"]["WearFeedbackResponse"];
export type WearFeedbackInput = components["schemas"]["WearFeedbackRequest"];
export type DecisionAction = components["schemas"]["RecommendationDecisionRequest"]["action"];
