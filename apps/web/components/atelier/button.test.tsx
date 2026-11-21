import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { Button } from "./button";

describe("Atelier Button", () => {
  it("defaults to a primary button of type button", async () => {
    const onClick = vi.fn();
    render(<Button onClick={onClick}>Wear it</Button>);
    const button = screen.getByRole("button", { name: "Wear it" });
    expect(button).toHaveAttribute("type", "button");
    expect(button).toHaveAttribute("data-variant", "primary");
    await userEvent.click(button);
    expect(onClick).toHaveBeenCalledOnce();
  });

  it.each(["soft", "outline", "text", "danger"] as const)("exposes the %s variant", (variant) => {
    render(<Button variant={variant}>Label</Button>);
    expect(screen.getByRole("button", { name: "Label" })).toHaveAttribute("data-variant", variant);
  });

  it("renders onto a link with asChild", () => {
    render(
      <Button asChild variant="outline" size="sm">
        <a href="#add">Add fragrance</a>
      </Button>,
    );
    const link = screen.getByRole("link", { name: "Add fragrance" });
    expect(link).toHaveAttribute("data-size", "sm");
    expect(link).not.toHaveAttribute("type");
  });

  it("stays in the layout when disabled", () => {
    render(<Button disabled>Saving…</Button>);
    expect(screen.getByRole("button", { name: "Saving…" })).toBeDisabled();
  });
});
