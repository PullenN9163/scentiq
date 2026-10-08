"use client";
import { ResponsiveContainer } from "recharts";
import type { ReactElement } from "react";
export function ChartContainer({ label, children }: { label: string; children: ReactElement }) {
  return <div className="chart-container" role="img" aria-label={label}><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>;
}
export function ChartTooltipContent({ active, label, payload }: { active?: boolean; label?: string | number; payload?: readonly { name?: string | number; value?: string | number; color?: string }[] }) {
  if (!active || !payload?.length) return null;
  return <div className="chart-tooltip"><strong>{label}</strong>{payload.map((item, index) => <p key={index}>{item.name}: <strong>{item.value}</strong></p>)}</div>;
}
