import { render, screen, fireEvent } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { Carousel } from "./carousel";

describe("Carousel", () => {
  it("supports keyboard navigation and names its controls", () => {
    render(<Carousel label="Alternatives"><p>One</p><p>Two</p></Carousel>);
    const region = screen.getByRole("region", { name: "Alternatives" });
    const scroll = vi.fn();
    Object.defineProperty(region, "scrollBy", { value: scroll });
    fireEvent.keyDown(region, { key: "ArrowRight" });
    expect(scroll).toHaveBeenCalled();
    expect(screen.getByRole("button", { name: "Next Alternatives" })).toBeInTheDocument();
  });
});
