"use client";
import { MotionConfig } from "motion/react";
import { Toaster } from "sonner";
import type { ReactNode } from "react";
import { motionTokens } from "@/lib/motion";

export function MotionProvider({ children }: { children: ReactNode }) {
  return <MotionConfig reducedMotion="user" transition={motionTokens.standard}>{children}<Toaster position="top-right" closeButton toastOptions={{ className: "scent-toast" }} /></MotionConfig>;
}
