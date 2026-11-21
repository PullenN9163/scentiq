import { act, render, screen } from "@testing-library/react";
import { toast } from "sonner";
import { describe, expect, it } from "vitest";

import { AtelierToaster } from "./toast";

describe("AtelierToaster", () => {
  it("shows success toasts with their words", async () => {
    render(<AtelierToaster />);
    act(() => { toast.success("Wear logged"); });
    expect(await screen.findByText("Wear logged")).toBeInTheDocument();
  });
});
