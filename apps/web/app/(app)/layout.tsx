import type { ReactNode } from "react";
import { AppShell } from "@/components/app-shell/app-shell";

export default function ProductLayout({ children }: { children: ReactNode }) {
  const premiumUI = process.env.SCENTIQ_PREMIUM_UI_ENABLED?.toLowerCase() !== "false";
  return <AppShell premiumUI={premiumUI}>{children}</AppShell>;
}
