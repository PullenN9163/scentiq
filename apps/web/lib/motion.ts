export const motionTokens = {
  micro: { duration: 0.15, ease: [0.22, 1, 0.36, 1] as const },
  standard: { duration: 0.22, ease: [0.22, 1, 0.36, 1] as const },
  panel: { duration: 0.3, ease: [0.22, 1, 0.36, 1] as const },
  sharedCard: { type: "spring" as const, stiffness: 360, damping: 35, bounce: 0.08 },
};
