"use client";

import "./experience.css";

/** Decorative movement never delays or obscures the content it surrounds. */
export function ExperienceBackdrop({ tone }: { tone: "blend" | "discover" | "insights" }) {
  return <div className={`experience-backdrop experience-backdrop--${tone}`} aria-hidden="true"><i /><i /><i /><span /></div>;
}
