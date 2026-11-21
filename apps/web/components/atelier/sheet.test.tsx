import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it } from "vitest";

import { Sheet } from "./sheet";

function Harness() {
  const [open, setOpen] = useState(false);
  return (
    <>
      <button onClick={() => setOpen(true)}>Open why this</button>
      <Sheet open={open} onOpenChange={setOpen} title="Why this" footer={<button>Done</button>}>
        <p>Score breakdown</p>
        <button>Inside</button>
      </Sheet>
    </>
  );
}

describe("Sheet", () => {
  it("opens as a dialog with its title and content", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Open why this" }));
    const dialog = await screen.findByRole("dialog", { name: "Why this" });
    expect(dialog).toHaveTextContent("Score breakdown");
    expect(screen.getByRole("button", { name: "Done" })).toBeInTheDocument();
  });

  it("closes on Escape and returns focus to the opener", async () => {
    render(<Harness />);
    const opener = screen.getByRole("button", { name: "Open why this" });
    await userEvent.click(opener);
    await screen.findByRole("dialog");
    await userEvent.keyboard("{Escape}");
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
    expect(opener).toHaveFocus();
  });

  it("closes from the labelled close button", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Open why this" }));
    await userEvent.click(await screen.findByRole("button", { name: "Close Why this" }));
    await waitFor(() => expect(screen.queryByRole("dialog")).not.toBeInTheDocument());
  });

  it("keeps focus inside while open", async () => {
    render(<Harness />);
    await userEvent.click(screen.getByRole("button", { name: "Open why this" }));
    const dialog = await screen.findByRole("dialog");
    for (let index = 0; index < 5; index += 1) {
      await userEvent.tab();
      expect(dialog).toContainElement(document.activeElement as HTMLElement);
    }
  });
});
