import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";

import { FragranceRow } from "./fragrance-row";

const fragrance = { id: "f1", name: "By the Fireplace", brand: "Maison Margiela", imageUrl: null };

describe("FragranceRow", () => {
  it("links the plate and name, keeping the trailing control separate", async () => {
    const plan = vi.fn();
    render(
      <FragranceRow
        fragrance={fragrance}
        accord="amber"
        caption="Tonight · Dinner"
        href="/collection/f1"
        trailing={<button onClick={plan}>Plan it</button>}
      />,
    );
    const link = screen.getByRole("link");
    expect(link).toHaveAttribute("href", "/collection/f1");
    expect(link).toHaveTextContent("By the Fireplace");
    expect(link).toHaveTextContent("Tonight · Dinner");
    expect(link).not.toContainElement(screen.getByRole("button", { name: "Plan it" }));
    await userEvent.click(screen.getByRole("button", { name: "Plan it" }));
    expect(plan).toHaveBeenCalledOnce();
  });

  it("opens through a button when given a handler", async () => {
    const onOpen = vi.fn();
    render(<FragranceRow fragrance={fragrance} accord="amber" onOpen={onOpen} />);
    await userEvent.click(screen.getByRole("button", { name: /By the Fireplace/ }));
    expect(onOpen).toHaveBeenCalledOnce();
  });

  it("can print the caption above the name", () => {
    render(<FragranceRow fragrance={fragrance} accord="amber" caption="Tonight" captionFirst />);
    const row = screen.getByTestId("fragrance-row");
    expect(row.textContent?.indexOf("Tonight")).toBeLessThan(row.textContent?.indexOf("By the Fireplace") ?? 0);
  });
});
