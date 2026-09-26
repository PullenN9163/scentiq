import { render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";

import DiscoverError from "./error";

describe("DiscoverError", () => {
  it("keeps a recommendation failure inside the Discover screen", () => {
    render(<DiscoverError error={new Error("service timeout")} reset={vi.fn()} />);

    expect(screen.getByRole("heading", { name: "Recommendations are taking a moment" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Try again" })).toBeInTheDocument();
  });
});
