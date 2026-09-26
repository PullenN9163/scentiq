import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import {
  collectionInsights,
  fragranceDetail,
  layeringSuggestion,
} from "@/test/catalog-fixtures";

import { AgentExperience } from "./agent-experience";

afterEach(cleanup);

describe("AgentExperience", () => {
  it("answers supported quick actions with deterministic collection context", async () => {
    const user = userEvent.setup();
    render(
      <AgentExperience
        owned={[fragranceDetail()]}
        insights={collectionInsights()}
        layering={[layeringSuggestion()]}
      />,
    );
    await user.click(screen.getByRole("button", { name: "What should I wear today?" }));
    expect(screen.getByText(/Source Scent is the strongest catalog-supported match/i)).toBeVisible();
  });

  it("does not answer from fictional collection data", async () => {
    const user = userEvent.setup();
    render(
      <AgentExperience owned={[]} insights={collectionInsights({ total_items: 0 })} layering={[]} />,
    );
    await user.click(screen.getByRole("button", { name: "What should I wear today?" }));
    expect(screen.getByText(/owned collection is empty/i)).toBeVisible();
  });
});
