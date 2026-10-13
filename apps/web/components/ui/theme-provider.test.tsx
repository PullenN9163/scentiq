import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, expect, it, vi } from "vitest";
import { ThemeProvider, AppearanceControl } from "./theme-provider";

afterEach(() => {cleanup(); document.cookie="scentiq-theme=; Max-Age=0; Path=/";});
it("persists an explicit theme and updates native color scheme", async () => {
  vi.stubGlobal("matchMedia", vi.fn(() => ({matches:false,addEventListener:vi.fn(),removeEventListener:vi.fn()})));
  render(<ThemeProvider><AppearanceControl /></ThemeProvider>);
  await userEvent.selectOptions(screen.getByRole("combobox", {name:"Appearance"}), "dark");
  expect(document.documentElement).toHaveAttribute("data-theme", "dark");
  expect(document.cookie).toContain("scentiq-theme=dark");
  await userEvent.selectOptions(screen.getByRole("combobox", {name:"Appearance"}), "system");
  expect(document.documentElement).toHaveAttribute("data-theme", "light");
});
it("provides accessible appearance choices in settings", async () => {
  render(<ThemeProvider initialPreference="light"><AppearanceControl expanded /></ThemeProvider>);
  await userEvent.click(screen.getByRole("radio", {name:"Dark"}));
  expect(screen.getByRole("radio", {name:"Dark"})).toBeChecked();
});
