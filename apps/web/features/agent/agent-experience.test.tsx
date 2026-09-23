import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { AgentExperience } from "./agent-experience";

afterEach(cleanup);

describe("AgentExperience", () => {
  it("answers supported quick actions with deterministic collection context", async () => {
    const user = userEvent.setup();
    render(<AgentExperience />);
    await user.click(screen.getByRole("button", { name: "What should I wear today?" }));
    expect(screen.getByText(/cedar after rain/i)).toBeVisible();
  });

  it("handles unsupported text honestly", async () => {
    const user = userEvent.setup();
    render(<AgentExperience />);
    await user.type(screen.getByLabelText(/ask scentiq/i), "Write me a poem");
    await user.click(screen.getByRole("button", { name: /send/i }));
    expect(screen.getByText(/demo currently supports/i)).toBeVisible();
  });
});
