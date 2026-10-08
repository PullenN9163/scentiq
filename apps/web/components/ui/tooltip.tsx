"use client";
import * as Primitive from "@radix-ui/react-tooltip";
import type { ReactNode } from "react";
export function Tooltip({ children, content }: { children: ReactNode; content: ReactNode }) {
  return <Primitive.Provider delayDuration={350}><Primitive.Root><Primitive.Trigger asChild>{children}</Primitive.Trigger><Primitive.Portal><Primitive.Content className="tooltip" sideOffset={6}>{content}<Primitive.Arrow /></Primitive.Content></Primitive.Portal></Primitive.Root></Primitive.Provider>;
}
