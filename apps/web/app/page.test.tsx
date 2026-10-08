import { render, screen } from "@testing-library/react";
import { expect, it, vi } from "vitest";

import Home from "./page";

// Signed out is the landing page's default audience.
vi.mock("@clerk/nextjs", () => ({
  SignedIn: () => null,
  SignedOut: ({ children }: { children: React.ReactNode }) => <>{children}</>,
}));

it("presents the ScentIQ product loop and routes signed-out visitors to sign-in", () => {
  render(<Home />);

  expect(screen.getByRole("heading", { level: 1, name: "ScentIQ" })).toBeVisible();
  expect(screen.getByText(/your life already has a rhythm/i)).toBeVisible();
  const signIn = screen.getAllByRole("link", { name: /sign in/i });
  expect(signIn).toHaveLength(2);
  expect(signIn[0]).toHaveAttribute("href", "/sign-in");
  expect(screen.getByText(/collection \+ schedule \+ weather/i)).toBeVisible();
});
