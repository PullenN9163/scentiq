import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { Badge } from "./badge";
import { Button } from "./button";
import { Progress } from "./progress";

describe("shared UI primitives", () => {
  it("keeps buttons operable while exposing the requested visual variant", () => {
    render(<Button variant="secondary">Choose scent</Button>);

    const button = screen.getByRole("button", { name: "Choose scent" });
    expect(button).toBeEnabled();
    expect(button).toHaveAttribute("data-variant", "secondary");
  });

  it("announces progress values accessibly", () => {
    render(<Progress value={82} label="Match score" />);

    expect(screen.getByRole("progressbar", { name: "Match score" })).toHaveAttribute(
      "aria-valuenow",
      "82",
    );
  });

  it("renders compact status badges", () => {
    render(<Badge>Demo mode</Badge>);
    expect(screen.getByText("Demo mode")).toBeInTheDocument();
  });
});
