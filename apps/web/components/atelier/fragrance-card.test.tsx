import { act, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it, vi } from "vitest";

import { FragranceCard } from "./fragrance-card";

const fragrance = { id: "f1", name: "Another 13", brand: "Le Labo", imageUrl: null };

afterEach(() => vi.useRealTimers());

describe("FragranceCard", () => {
  it("makes the whole card open the fragrance", () => {
    render(<FragranceCard fragrance={fragrance} accord="musk" href="/collection/f1" status="Nearly empty" />);
    expect(screen.getByRole("link", { name: "Another 13" })).toHaveAttribute("href", "/collection/f1");
    expect(screen.getByTestId("fragrance-card")).toHaveTextContent("Le Labo · Nearly empty");
  });

  it("offers quick actions that are reachable by keyboard", async () => {
    const wear = vi.fn();
    render(
      <FragranceCard
        fragrance={fragrance}
        accord="musk"
        href="/collection/f1"
        actions={[{ label: "Wear it", onSelect: wear }, { label: "Layer it", href: "/layering?a=f1" }]}
      />,
    );
    await userEvent.tab();
    expect(screen.getByRole("button", { name: "Wear it" })).toHaveFocus();
    await userEvent.keyboard("{Enter}");
    expect(wear).toHaveBeenCalledOnce();
    expect(screen.getByRole("link", { name: "Layer it" })).toHaveAttribute("href", "/layering?a=f1");
  });

  it("reveals the quick actions on a long press", () => {
    vi.useFakeTimers();
    render(<FragranceCard fragrance={fragrance} accord="musk" href="/x" actions={[{ label: "Wear it" }]} />);
    const card = screen.getByTestId("fragrance-card");
    fireEvent.pointerDown(card, { pointerType: "touch" });
    act(() => { vi.advanceTimersByTime(500); });
    expect(card).toHaveAttribute("data-actions-open", "true");
  });

  it("adds no quick actions when none are given", () => {
    render(<FragranceCard fragrance={fragrance} accord="musk" href="/x" />);
    expect(screen.queryByRole("button")).not.toBeInTheDocument();
  });
});
