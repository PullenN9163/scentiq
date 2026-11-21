import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { RemoteImagesProvider } from "@/components/catalog-image";

import { Plate } from "./plate";
import { plateFragrance } from "./plate-fragrance";

const fragrance = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Another 13",
  brand: "Le Labo",
  imageUrl: "https://fimgs.net/mdimg/perfume/375x500.1.jpg",
};

describe("Plate", () => {
  it("blends the photo onto the accord plate", () => {
    const { container } = render(<Plate fragrance={fragrance} accord="musk" />);
    const plate = container.firstElementChild as HTMLElement;
    expect(plate).toHaveAttribute("data-accord", "musk");
    expect(plate.style.getPropertyValue("--af")).toBe("var(--accord-musk-field)");
    expect(screen.getByRole("img", { name: "Another 13 by Le Labo" })).toBeInTheDocument();
  });

  it("shows the house name, not a drawn bottle, when there is no photo", () => {
    render(<Plate fragrance={{ ...fragrance, imageUrl: null }} accord="neutral" />);
    expect(screen.getByTestId("plate-fallback")).toHaveTextContent("Le Labo");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("falls back when the photo fails to load", () => {
    render(<Plate fragrance={fragrance} accord="woody" />);
    fireEvent.error(screen.getByRole("img"));
    expect(screen.getByTestId("plate-fallback")).toHaveTextContent("Le Labo");
  });

  it("respects the remote image switch but still shows private uploads", () => {
    const { rerender } = render(
      <RemoteImagesProvider enabled={false}>
        <Plate fragrance={fragrance} accord="woody" />
      </RemoteImagesProvider>,
    );
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
    rerender(
      <RemoteImagesProvider enabled={false}>
        <Plate fragrance={{ ...fragrance, imageUrl: `/api/fragrances/${fragrance.id}/image` }} accord="woody" />
      </RemoteImagesProvider>,
    );
    expect(screen.getByRole("img")).toBeInTheDocument();
  });

  it("uses an empty alt when the name is printed beside it", () => {
    render(<Plate fragrance={fragrance} accord="woody" decorative />);
    expect(screen.getByRole("presentation")).toHaveAttribute("alt", "");
  });

  it("shapes catalog fragrances", () => {
    expect(
      plateFragrance({ id: "1", name: "A", brand: { name: "B" }, image_url: null }),
    ).toEqual({ id: "1", name: "A", brand: "B", imageUrl: null });
  });
});
