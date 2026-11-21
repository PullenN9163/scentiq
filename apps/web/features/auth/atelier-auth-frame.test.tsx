import { render, screen } from "@testing-library/react";
import { expect, it } from "vitest";

import { AtelierAuthFrame } from "./atelier-auth-frame";

it("titles the sign-in form and renders the Clerk form beside it", () => {
  render(
    <AtelierAuthFrame mode="sign-in">
      <form aria-label="Clerk form" />
    </AtelierAuthFrame>,
  );

  expect(screen.getByRole("heading", { level: 1, name: "Welcome back" })).toBeVisible();
  expect(screen.getByText("Sign in to see what to wear today.")).toBeVisible();
  expect(screen.getByRole("form", { name: "Clerk form" })).toBeVisible();
  expect(screen.getByRole("link", { name: "ScentIQ" })).toHaveAttribute("href", "/");
});

it("titles the sign-up form for a new shelf", () => {
  render(
    <AtelierAuthFrame mode="sign-up">
      <form aria-label="Clerk form" />
    </AtelierAuthFrame>,
  );

  expect(screen.getByRole("heading", { level: 1, name: "Make a shelf" })).toBeVisible();
  expect(screen.getByRole("form", { name: "Clerk form" })).toBeVisible();
});
