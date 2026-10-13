import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import type { ReactNode } from "react";
import { cookies } from "next/headers";
import { ThemeProvider } from "@/components/ui/theme-provider";
import { themeInitScript, type ThemePreference } from "@/lib/theme";

import { RemoteImagesProvider } from "@/components/catalog-image";
import { MotionProvider } from "@/components/ui/motion-provider";

import "./globals.css";

export const metadata: Metadata = {
  title: "ScentIQ",
  description: "Personal fragrance intelligence for every day and occasion.",
};

export default async function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  const savedTheme = (await cookies()).get("scentiq-theme")?.value;
  const preference:ThemePreference = savedTheme === "light" || savedTheme === "dark" ? savedTheme : "system";
  // Bracket notation keeps this a runtime lookup in the standalone server, so
  // operators can disable hotlinks with configuration rather than a new image.
  const remoteImagesEnabled = process.env["NEXT_PUBLIC_CATALOG_REMOTE_IMAGES"] !== "false";
  return (
      <html lang="en" data-scroll-behavior="smooth" data-theme={preference === "system" ? undefined : preference} suppressHydrationWarning>
        <head><script dangerouslySetInnerHTML={{__html:themeInitScript}} /></head>
        <body>
          <ThemeProvider initialPreference={preference}><ClerkProvider appearance={{variables:{colorPrimary:"var(--primary)",colorBackground:"var(--surface)",colorText:"var(--foreground)",colorTextSecondary:"var(--muted-foreground)",colorInputBackground:"var(--surface-elevated)",colorInputText:"var(--foreground)",colorNeutral:"var(--foreground)",borderRadius:"1rem",fontFamily:"-apple-system, BlinkMacSystemFont, Segoe UI, sans-serif"},elements:{card:"auth-card",footer:"auth-footer",formButtonPrimary:"auth-primary",socialButtonsBlockButton:"auth-social"}}}>
          <MotionProvider><RemoteImagesProvider enabled={remoteImagesEnabled}>{children}</RemoteImagesProvider></MotionProvider>
          </ClerkProvider></ThemeProvider>
        </body>
      </html>
  );
}
