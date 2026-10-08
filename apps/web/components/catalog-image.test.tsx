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
  it("retries a replaced private image after an earlier load failure", () => {
    const url = `/api/fragrances/${props.id}/image?v=1`;
    const { rerender } = render(<CatalogImage {...props} imageUrl={url} />);
    fireEvent.error(screen.getByRole("img"));
    rerender(<CatalogImage {...props} imageUrl={`/api/fragrances/${props.id}/image?v=2`} />);
    expect(screen.getByRole("img")).toBeInTheDocument();
  });
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
