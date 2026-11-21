const easeOutQuint = [0.22, 1, 0.36, 1] as const;

export const motionTokens = {
  micro: { duration: 0.15, ease: easeOutQuint },
  standard: { duration: 0.22, ease: easeOutQuint },
  panel: { duration: 0.3, ease: easeOutQuint },
  sharedCard: { type: "spring" as const, stiffness: 360, damping: 35, bounce: 0.08 },
  /** Press, hover, toggle, focus. */
  instant: { duration: 0.12, ease: "easeOut" as const },
  /** Chips, segments, toasts, fades. */
  quick: { duration: 0.2, ease: easeOutQuint },
  /** Sheets, panels, page content arriving. */
  settle: { duration: 0.3, ease: easeOutQuint },
  /** Shared elements, sheet drag, segment thumb. */
  springSoft: { type: "spring" as const, stiffness: 260, damping: 30 },
  /** Blend studio drag and drop, the wear moment. */
  springLively: { type: "spring" as const, stiffness: 420, damping: 24 },
  /** Signature liquid and mist only (900 to 1600ms). */
  flow: { duration: 0.9, ease: "easeInOut" as const },
};
