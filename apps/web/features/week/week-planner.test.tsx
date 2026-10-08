import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { WeekPlanner } from "./week-planner";
import type { WearPlan } from "@/types/wear-intelligence";
vi.mock("@/features/recommendations/recommendation-card",()=>({RecommendationCard: ({recommendation}: {recommendation:{score:number}})=><p>Backend match {recommendation.score}</p>}));
afterEach(cleanup);
const plan: WearPlan = {timezone:"UTC",local_date:"2026-10-07",gaps:["Weather unavailable; weather scoring is neutral."],recommendations:[]};
it("renders seven day sections without inventing recommendations",()=> {
  render(<WeekPlanner plan={plan}/>);
  expect(screen.getAllByTestId("week-day")).toHaveLength(7);
  expect(screen.getByText("Add an owned fragrance before planning a week.")).toBeVisible();
  expect(screen.getByText(/Weather unavailable/)).toBeVisible();
  expect(screen.queryByText(/Backend match/)).not.toBeInTheDocument();
});
