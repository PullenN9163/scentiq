import { afterEach, expect, it, vi } from "vitest";

import { AppShell } from "@/components/app-shell/app-shell";
import { AtelierShell } from "@/components/atelier-shell/atelier-shell";

afterEach(() => vi.unstubAllEnvs());

it.each(["false", "False"])("passes premium styling rollback through for %s", async (flag) => {
  vi.stubEnv("SCENTIQ_PREMIUM_UI_ENABLED", flag);
  vi.resetModules();
  const { default: ProductLayout } = await import("./layout");
  const element = ProductLayout({ children: <p>Page content</p> });

  expect(element.props.premiumUI).toBe(false);
});

it.each(["true", "TRUE", "True"])("renders the Atelier shell when the flag is %s", async (flag) => {
  vi.stubEnv("SCENTIQ_ATELIER_UI_ENABLED", flag);
  const { default: ProductLayout } = await import("./layout");
  const element = ProductLayout({ children: <p>Page content</p> });

  expect((element.type as { name: string }).name).toBe(AtelierShell.name);
});

it.each([undefined, "", "false", "yes"])("keeps the current shell when the flag is %s", async (flag) => {
  if (flag !== undefined) vi.stubEnv("SCENTIQ_ATELIER_UI_ENABLED", flag);
  const { default: ProductLayout } = await import("./layout");
  const element = ProductLayout({ children: <p>Page content</p> });

  expect((element.type as { name: string }).name).toBe(AppShell.name);
});
