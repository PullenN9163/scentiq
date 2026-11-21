import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Chip } from "./chip";

describe("Chip", () => {
  it("renders read-only context and note chips as text", () => {
    render(
      <>
        <Chip>45°F cloudy</Chip>
        <Chip variant="note">Cedar</Chip>
      </>,
    );
    expect(screen.getByText("45°F cloudy")).toHaveAttribute("data-variant", "context");
    expect(screen.getByText("Cedar")).toHaveAttribute("data-variant", "note");
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });

  it("exposes the pressed state of a choice chip", async () => {
    const onClick = vi.fn();
    const { rerender } = render(
      <Chip variant="choice" pressed={false} onClick={onClick}>
        Woody
      </Chip>,
    );
    const chip = screen.getByRole("button", { name: "Woody" });
    expect(chip).toHaveAttribute("aria-pressed", "false");
    await userEvent.click(chip);
    expect(onClick).toHaveBeenCalledOnce();
    rerender(
      <Chip variant="choice" pressed onClick={onClick}>
        Woody
      </Chip>,
    );
    expect(screen.getByRole("button", { name: "Woody" })).toHaveAttribute("aria-pressed", "true");
  });
});
