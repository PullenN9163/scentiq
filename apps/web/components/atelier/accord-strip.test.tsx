import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { AccordStrip, stripSegments } from "./accord-strip";

describe("AccordStrip", () => {
  it("keeps five accords and groups the rest as Other", () => {
    const segments = stripSegments(["Woody", "Fresh", "Amber", "Floral", "Spicy", "Green", "Citrus"].map((label, index) => ({ label, share: 7 - index })));
    expect(segments.map((segment) => segment.label)).toEqual(["Woody", "Fresh", "Amber", "Floral", "Spicy", "Other"]);
    expect(segments.reduce((sum, segment) => sum + segment.share, 0)).toBeCloseTo(1);
  });

  it("labels every segment in text", () => {
    render(<AccordStrip accords={[{ label: "Musky", share: 0.55 }, { label: "Woody", share: 0.45 }]} />);
    expect(screen.getByText("Musky 55% · Woody 45%")).toBeInTheDocument();
  });

  it("renders nothing without data", () => {
    const { container } = render(<AccordStrip accords={[]} />);
    expect(container).toBeEmptyDOMElement();
  });
});
