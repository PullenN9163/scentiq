import { ClerkProvider } from "@clerk/nextjs";
import type { Metadata } from "next";
import type { ReactNode } from "react";

import { RemoteImagesProvider } from "@/components/catalog-image";

import "./globals.css";

export const metadata: Metadata = {
  title: "ScentIQ",
  description: "Personal fragrance intelligence for every day and occasion.",
};

export default function RootLayout({ children }: Readonly<{ children: ReactNode }>) {
  // Bracket notation keeps this a runtime lookup in the standalone server, so
  // operators can disable hotlinks with configuration rather than a new image.
  const remoteImagesEnabled = process.env["NEXT_PUBLIC_CATALOG_REMOTE_IMAGES"] !== "false";
  return (
    <ClerkProvider>
      <html lang="en" data-scroll-behavior="smooth">
        <body>
          <RemoteImagesProvider enabled={remoteImagesEnabled}>{children}</RemoteImagesProvider>
        </body>
      </html>
    </ClerkProvider>
  );
}
