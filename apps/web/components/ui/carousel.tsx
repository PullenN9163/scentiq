"use client";
import { Children, useRef, type ReactNode } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Button } from "./button";

export function Carousel({ label, children, className = "" }: { label: string; children: ReactNode; className?: string }) {
  const ref = useRef<HTMLDivElement>(null);
  const move = (direction: number) => ref.current?.scrollBy({ left: direction * (ref.current.clientWidth || 320), behavior: window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ? "instant" : "smooth" });
  return <div className={`carousel ${className}`}><div ref={ref} role="region" aria-label={label} aria-roledescription="carousel" tabIndex={0} className="carousel__track" onKeyDown={(event) => { if (event.target !== event.currentTarget) return; if (event.key === "ArrowLeft" || event.key === "ArrowRight") { event.preventDefault(); move(event.key === "ArrowRight" ? 1 : -1); } }}>{Children.map(children, (child, index) => <div role="group" aria-roledescription="slide" aria-label={`${index + 1} of ${Children.count(children)}`} className="carousel__slide">{child}</div>)}</div><div className="cluster carousel__controls"><Button variant="secondary" aria-label={`Previous ${label}`} onClick={() => move(-1)}><ArrowLeft size={16} /></Button><Button variant="secondary" aria-label={`Next ${label}`} onClick={() => move(1)}><ArrowRight size={16} /></Button></div></div>;
}
