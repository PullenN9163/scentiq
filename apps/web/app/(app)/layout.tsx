import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell/app-shell";
import { AtelierShell } from "@/components/atelier-shell/atelier-shell";
import { isAtelierEnabled } from "@/lib/atelier-flag";

export default function ProductLayout({ children }: { children: ReactNode }) {
  // SCENTIQ_ATELIER_UI_ENABLED="true" (any case) switches to the Atelier shell.
  if (isAtelierEnabled()) return <AtelierShell>{children}</AtelierShell>;
  const premiumUI = process.env.SCENTIQ_PREMIUM_UI_ENABLED?.toLowerCase() !== "false";
  return <AppShell premiumUI={premiumUI}>{children}</AppShell>;
}
