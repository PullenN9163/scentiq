"use client";

import Image from "next/image";
import { createContext, useContext, useState, type ReactNode } from "react";

import { toneFor } from "@/lib/tone";

const RemoteImagesContext = createContext(true);

export function RemoteImagesProvider({
  enabled,
  children,
}: {
  enabled: boolean;
  children: ReactNode;
}) {
  return <RemoteImagesContext value={enabled}>{children}</RemoteImagesContext>;
}

export function CatalogImage({
  id,
  name,
  brand,
  imageUrl,
  className,
}: {
  id: string;
  name: string;
  brand: string;
  imageUrl: string | null;
  className?: string;
}) {
  const [failed, setFailed] = useState(false);
  const remoteEnabled = useContext(RemoteImagesContext);
  if (!remoteEnabled || !imageUrl || failed) {
    return (
      <div
        className={className}
        style={{ "--scent-tone": toneFor(id) } as React.CSSProperties}
        data-testid="catalog-image-fallback"
      >
        <span>{brand}</span>
        <strong>{name}</strong>
      </div>
    );
  }
  return (
    <div className={className}>
      <Image
        src={imageUrl}
        alt={`${name} by ${brand}`}
        width={375}
        height={500}
        loading="lazy"
        onError={() => setFailed(true)}
      />
    </div>
  );
}
