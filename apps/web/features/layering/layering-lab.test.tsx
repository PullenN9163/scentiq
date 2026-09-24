import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import { LayeringLab } from "./layering-lab";

afterEach(cleanup);

describe("LayeringLab", () => {
  it("honors preselection and swaps the pair", async () => {
    const user = userEvent.setup();
    render(<LayeringLab initialA="cedar-after-rain" />);
    expect(screen.getByLabelText("Fragrance A")).toHaveValue("cedar-after-rain");
    await user.click(screen.getByRole("button", { name: /swap fragrances/i }));
    expect(screen.getByLabelText("Fragrance B")).toHaveValue("cedar-after-rain");
  });

  it("changes guidance mode and keeps the pair in the preview only", async () => {
    const user = userEvent.setup();
    render(<LayeringLab />);
    await user.click(screen.getByRole("button", { name: "Experimental" }));
    expect(screen.getByText(/experimental guidance/i)).toBeVisible();
    await user.click(screen.getByRole("button", { name: /keep in this preview/i }));
    // The preview must not claim the combination was saved.
    expect(screen.getByRole("status")).toHaveTextContent(/was not saved/i);
  });
});
