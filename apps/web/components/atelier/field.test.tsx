import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { describe, expect, it, vi } from "vitest";

import { Field, Stepper, Switch, TextInput } from "./field";

function StepperHarness() {
  const [value, setValue] = useState(29);
  return <Stepper label="Sprays" min={1} max={30} value={value} onChange={setValue} />;
}

describe("Atelier fields", () => {
  it("labels a text input and shows its error", () => {
    render(<Field label="Location" htmlFor="loc" error="Enter a city."><TextInput id="loc" invalid /></Field>);
    expect(screen.getByLabelText("Location")).toHaveAttribute("aria-invalid", "true");
    expect(screen.getByRole("alert")).toHaveTextContent("Enter a city.");
  });

  it("steps within its bounds", async () => {
    render(<StepperHarness />);
    const input = screen.getByRole("spinbutton", { name: "Sprays" });
    await userEvent.click(screen.getByRole("button", { name: "More sprays" }));
    expect(input).toHaveValue(30);
    expect(screen.getByRole("button", { name: "More sprays" })).toBeDisabled();
    await userEvent.click(screen.getByRole("button", { name: "Fewer sprays" }));
    expect(input).toHaveValue(29);
  });

  it("toggles a switch", async () => {
    const onChange = vi.fn();
    render(<Switch label="Reduce effects" checked={false} onCheckedChange={onChange} />);
    await userEvent.click(screen.getByRole("switch", { name: "Reduce effects" }));
    expect(onChange).toHaveBeenCalledWith(true);
  });
});
