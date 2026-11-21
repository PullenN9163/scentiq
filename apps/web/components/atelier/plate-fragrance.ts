// Plain module on purpose: server components call plateFragrance, which they cannot do
// if it is exported from a "use client" file such as plate.tsx.

export type PlateFragrance = {
  id: string;
  name: string;
  brand: string;
  imageUrl: string | null;
};

/** Shape a catalog fragrance for a plate. */
export function plateFragrance(fragrance: {
  id: string;
  name: string;
  brand: { name: string };
  image_url?: string | null;
}): PlateFragrance {
  return { id: fragrance.id, name: fragrance.name, brand: fragrance.brand.name, imageUrl: fragrance.image_url ?? null };
}
