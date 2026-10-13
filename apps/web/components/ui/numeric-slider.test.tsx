import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { NumericSlider } from "./numeric-slider";

afterEach(cleanup);
it("synchronizes the range and numeric field without submitting two values", async () => {
  render(<form data-testid="form"><label htmlFor="sprays">Sprays</label><NumericSlider id="sprays" name="sprays" label="Sprays" min={1} max={30} defaultValue="3" /></form>);
  fireEvent.change(screen.getByRole("slider"), {target:{value:"7"}});
  expect(screen.getByRole("spinbutton")).toHaveValue(7);
  await userEvent.clear(screen.getByRole("spinbutton"));
  expect(new FormData(screen.getByTestId("form") as HTMLFormElement).getAll("sprays")).toEqual([""]);
  expect(screen.getByRole("slider")).toHaveAttribute("aria-valuetext", "Not specified");
});
it("preserves invalid typed values for validation and restores submitted defaults", () => {
  const {rerender} = render(<NumericSlider id="amount" label="Remaining (ml)" min={0} max={100} defaultValue="20" />);
  fireEvent.change(screen.getByRole("spinbutton"), {target:{value:"120"}});
  expect(screen.getByRole("spinbutton")).toHaveValue(120);
  expect(screen.getByRole("slider")).toHaveValue("100");
  rerender(<NumericSlider id="amount" label="Remaining (ml)" min={0} max={100} defaultValue="45" />);
  expect(screen.getByRole("spinbutton")).toHaveValue(45);
});
it("supports controlled recommendation values", () => {
  const change = vi.fn();
  render(<NumericSlider id="controlled" label="Sprays" min={1} max={30} value={4} onValueChange={change} />);
  fireEvent.change(screen.getByRole("slider"), {target:{value:"5"}});
  expect(change).toHaveBeenCalledWith("5");
});
it("retains submitted values through a native action reset until new defaults arrive",()=>{
  render(<form data-testid="reset-form"><NumericSlider id="reset-value" label="Sprays" name="sprays" min={1} max={30} defaultValue="4"/></form>);
  fireEvent.change(screen.getByRole("spinbutton"),{target:{value:"7"}});
  fireEvent.reset(screen.getByTestId("reset-form"));
  expect(screen.getByRole("spinbutton")).toHaveValue(7);
  expect(screen.getByRole("slider")).toHaveValue("7");
});
