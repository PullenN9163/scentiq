"use client";

import { useState, type CSSProperties, type InputHTMLAttributes } from "react";

type NumericSliderProps = Omit<InputHTMLAttributes<HTMLInputElement>, "type" | "value" | "defaultValue" | "min" | "max" | "step" | "onChange"> & {
  label: string; min: number; max: number; step?: number;
  value?: number | string; defaultValue?: string; onValueChange?: (value:string)=>void;
  inputMax?: number | null;
};

export function NumericSlider({label,min,max,step=1,value,defaultValue="",onValueChange,inputMax=max,...props}: NumericSliderProps) {
  const [internal,setInternal] = useState(defaultValue);
  const [previousDefault,setPreviousDefault] = useState(defaultValue);
  if (previousDefault !== defaultValue) {setPreviousDefault(defaultValue);setInternal(defaultValue);}
  // React form actions reset native fields even when returning validation
  // errors. Keep the controlled value until the action supplies new defaults.
  const current = value === undefined ? internal : String(value);
  const rangeValue = Math.min(max, Math.max(min, current === "" || !Number.isFinite(Number(current)) ? min : Number(current)));
  function change(next:string) {if(value === undefined) setInternal(next);onValueChange?.(next);}
  return <div className="numeric-slider">
    <input type="range" aria-label={`${label} slider`} aria-valuetext={current === "" ? "Not specified" : `${current}`} aria-describedby={props["aria-describedby"]} min={min} max={max} step={step} value={rangeValue} disabled={props.disabled} onChange={event=>change(event.target.value)} style={{"--range-progress":`${((rangeValue-min)/(max-min))*100}%`} as CSSProperties}/>
    <input {...props} className="input numeric-slider__value" type="number" aria-label={props.id ? undefined : label} min={min} max={inputMax ?? undefined} step={step} value={current} onChange={event=>change(event.target.value)}/>
  </div>;
}
