/**
 * Signature mist: a short canvas particle burst tinted with an accord color.
 * Created on demand, removed when it ends, skipped under reduced motion or
 * the "Reduce effects" setting. Used for the wear-logged moment and in the
 * Blend studio only.
 */

export type MistOptions = {
  /** Where the burst starts (viewport coordinates). */
  from: { x: number; y: number };
  /** Optional point the mist drifts toward. */
  to?: { x: number; y: number };
  /** Any CSS color. */
  color: string;
  /** 24 to 40; halved on low-core devices. */
  particles?: number;
  durationMs?: number;
};

export function effectsReduced(): boolean {
  if (typeof window === "undefined") return true;
  if (document.documentElement.dataset.effects === "reduced") return true;
  return window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;
}

/** Center of an element's box, in viewport coordinates. */
export function centerOf(element: Element): { x: number; y: number } {
  const box = element.getBoundingClientRect();
  return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
}

/** Resolve a CSS custom property (such as --ac) on an element to a color. */
export function resolveColor(element: Element, property: string, fallback = "#8a5a3c"): string {
  const value = getComputedStyle(element).getPropertyValue(property).trim();
  return value || fallback;
}

let lowPowerFrames = 0;

/** Play one burst. Resolves when the canvas has been removed. */
export function playMist({ from, to, color, particles = 32, durationMs = 900 }: MistOptions): Promise<void> {
  if (effectsReduced() || typeof document === "undefined") return Promise.resolve();
  const canvas = document.createElement("canvas");
  const context = canvas.getContext("2d");
  if (!context) return Promise.resolve();

  let count = Math.max(24, Math.min(40, particles));
  if ((navigator.hardwareConcurrency ?? 8) <= 4 || lowPowerFrames > 2) count = Math.round(count / 2);

  const ratio = Math.min(window.devicePixelRatio || 1, 2);
  const width = window.innerWidth;
  const height = window.innerHeight;
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  canvas.setAttribute("aria-hidden", "true");
  Object.assign(canvas.style, { position: "fixed", inset: "0", width: `${width}px`, height: `${height}px`, pointerEvents: "none", zIndex: "120" });
  document.body.append(canvas);
  context.scale(ratio, ratio);

  const direction = to ? Math.atan2(to.y - from.y, to.x - from.x) : -Math.PI / 2;
  const reach = to ? Math.min(260, Math.hypot(to.x - from.x, to.y - from.y)) : 140;
  const motes = Array.from({ length: count }, () => {
    const angle = direction + (Math.random() - 0.5) * 1.6;
    const speed = reach * (0.45 + Math.random() * 0.75);
    return { angle, speed, size: 2 + Math.random() * 5, drift: (Math.random() - 0.5) * 40, delay: Math.random() * 0.18 };
  });

  return new Promise((resolve) => {
    const start = performance.now();
    let last = start;
    const frame = (now: number) => {
      if (now - last > 34) lowPowerFrames += 1;
      last = now;
      const t = Math.min(1, (now - start) / durationMs);
      context.clearRect(0, 0, width, height);
      context.fillStyle = color;
      for (const mote of motes) {
        const local = Math.max(0, Math.min(1, (t - mote.delay) / (1 - mote.delay)));
        if (local <= 0) continue;
        const eased = 1 - (1 - local) ** 3;
        const x = from.x + Math.cos(mote.angle) * mote.speed * eased + mote.drift * local;
        const y = from.y + Math.sin(mote.angle) * mote.speed * eased - 20 * local;
        context.globalAlpha = (1 - local) * 0.55;
        context.beginPath();
        context.arc(x, y, mote.size * (1 + local * 1.8), 0, Math.PI * 2);
        context.fill();
      }
      if (t < 1) requestAnimationFrame(frame);
      else {
        canvas.remove();
        resolve();
      }
    };
    requestAnimationFrame(frame);
  });
}
