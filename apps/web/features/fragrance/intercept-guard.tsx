"use client";

import { usePathname } from "next/navigation";
import type { ReactNode } from "react";

/**
 * On a soft navigation away from /collection/[id], Next keeps the sheet slot's
 * last content. Render it only while the address is still that fragrance.
 */
export function InterceptGuard({ id, children }: { id: string; children: ReactNode }) {
  const pathname = usePathname();
  return pathname === `/collection/${id}` ? children : null;
}
