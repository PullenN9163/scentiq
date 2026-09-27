import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";

import { CatalogImage, RemoteImagesProvider } from "./catalog-image";

const props = {
  id: "11111111-1111-4111-8111-111111111111",
  name: "Source Scent",
  brand: "Source House",
  imageUrl: "https://fimgs.net/mdimg/perfume/375x500.1.jpg",
};

describe("CatalogImage", () => {
  it("uses deterministic art when remote images are disabled", () => {
    render(
      <RemoteImagesProvider enabled={false}>
        <CatalogImage {...props} />
      </RemoteImagesProvider>,
    );

    expect(screen.getByTestId("catalog-image-fallback")).toHaveTextContent("Source Scent");
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("falls back when a remote image fails", () => {
    render(<CatalogImage {...props} />);
    fireEvent.error(screen.getByRole("img", { name: "Source Scent by Source House" }));
    expect(screen.getByTestId("catalog-image-fallback")).toBeVisible();
  });
});
