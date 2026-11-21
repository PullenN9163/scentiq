import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { SegmentedControl } from "./segmented-control";

describe("SegmentedControl", () => {
  it("switches with pressed buttons and shows counts", async () => {
    const onChange = vi.fn();
    render(
      <SegmentedControl
        label="Collection view"
        value="shelf"
        onChange={onChange}
        segments={[{ value: "shelf", label: "Shelf", count: 26 }, { value: "wishlist", label: "Wishlist", count: 3 }]}
      />,
    );
    expect(screen.getByRole("group", { name: "Collection view" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Shelf 26" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Wishlist 3" }));
    expect(onChange).toHaveBeenCalledWith("wishlist");
  });

  it("renders link segments as navigation with aria-current", () => {
    render(
      <SegmentedControl
        label="Primary navigation"
        value="week"
        segments={[{ value: "today", label: "Today", href: "/dashboard" }, { value: "week", label: "Week", href: "/week" }]}
      />,
    );
    expect(screen.getByRole("navigation", { name: "Primary navigation" })).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Week" })).toHaveAttribute("aria-current", "page");
    expect(screen.getByRole("link", { name: "Today" })).not.toHaveAttribute("aria-current");
  });
});
