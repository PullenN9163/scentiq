"use client";
import { MotionConfig } from "motion/react";
import { Toaster } from "sonner";
import type { ReactNode } from "react";
import { AtelierToaster } from "@/components/atelier/toast";
import { motionTokens } from "@/lib/motion";

export function MotionProvider({ children, atelier = false, reduceEffects = false }: { children: ReactNode; atelier?: boolean; reduceEffects?: boolean }) {
  return <MotionConfig reducedMotion={reduceEffects ? "always" : "user"} transition={motionTokens.standard}>{children}{atelier ? <AtelierToaster /> : <Toaster position="top-right" closeButton toastOptions={{ className: "scent-toast" }} />}</MotionConfig>;
}
