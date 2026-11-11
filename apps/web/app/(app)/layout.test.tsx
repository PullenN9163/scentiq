import { afterEach, expect, it, vi } from "vitest";

afterEach(() => vi.unstubAllEnvs());

it.each(["false", "False"])("passes premium styling rollback through for %s", async (flag) => {
  vi.stubEnv("SCENTIQ_PREMIUM_UI_ENABLED", flag);
  vi.resetModules();
  const { default: ProductLayout } = await import("./layout");
  const element = ProductLayout({ children: <p>Page content</p> });

  expect(element.props.premiumUI).toBe(false);
});
