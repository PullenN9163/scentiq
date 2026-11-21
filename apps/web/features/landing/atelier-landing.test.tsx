import { render, screen } from "@testing-library/react";
import type { ReactNode } from "react";
import { beforeEach, expect, it, vi } from "vitest";

import { AtelierLanding } from "./atelier-landing";

const auth = vi.hoisted(() => ({ signedIn: false }));

vi.mock("@clerk/nextjs", () => ({
  SignedIn: ({ children }: { children: ReactNode }) => (auth.signedIn ? <>{children}</> : null),
  SignedOut: ({ children }: { children: ReactNode }) => (auth.signedIn ? null : <>{children}</>),
}));

beforeEach(() => {
  auth.signedIn = false;
});

it("offers sign-in and sign-up to signed-out visitors", () => {
  render(<AtelierLanding />);

  expect(screen.getByRole("heading", { level: 1, name: "Wear the scent your day calls for." })).toBeVisible();
  expect(screen.getAllByRole("link", { name: "Get started" })[0]).toHaveAttribute("href", "/sign-up");
  expect(screen.getAllByRole("link", { name: "Sign in" })[0]).toHaveAttribute("href", "/sign-in");
  expect(screen.queryByRole("link", { name: "Open ScentIQ" })).not.toBeInTheDocument();
});

it("sends signed-in members to the app", () => {
  auth.signedIn = true;
  render(<AtelierLanding />);

  expect(screen.getAllByRole("link", { name: "Open ScentIQ" })[0]).toHaveAttribute("href", "/dashboard");
  expect(screen.queryByRole("link", { name: "Get started" })).not.toBeInTheDocument();
  expect(screen.queryByRole("link", { name: "Sign in" })).not.toBeInTheDocument();
});

it("keeps the three steps and the Blend studio band", () => {
  render(<AtelierLanding />);

  expect(screen.getByRole("heading", { name: "Add what you own" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Share your day" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Wear the pick" })).toBeVisible();
  expect(screen.getByRole("heading", { name: "Blend two scents into one." })).toBeVisible();
  expect(screen.getByRole("link", { name: "Open the studio" })).toHaveAttribute("href", "/layering");
});
