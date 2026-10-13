"use client";

import { createContext, useContext, useEffect, useId, useState, type ReactNode } from "react";
import { Monitor, Moon, Sun } from "lucide-react";

import type { ThemePreference } from "@/lib/theme";
export type { ThemePreference } from "@/lib/theme";
const choices = [{value:"system", label:"System", icon:Monitor}, {value:"light", label:"Light", icon:Sun}, {value:"dark", label:"Dark", icon:Moon}] as const;
const ThemeContext = createContext<{preference:ThemePreference; setPreference:(value:ThemePreference)=>void}>({preference:"system",setPreference:()=>{}});

export function ThemeProvider({children,initialPreference="system"}: {children:ReactNode; initialPreference?:ThemePreference}) {
  const [preference,setPreference] = useState<ThemePreference>(initialPreference);
  useEffect(() => {
    const media = window.matchMedia("(prefers-color-scheme: dark)");
    const apply = () => {document.documentElement.dataset.theme = preference === "system" ? (media.matches ? "dark" : "light") : preference;};
    apply();
    media.addEventListener("change", apply);
    return () => media.removeEventListener("change", apply);
  }, [preference]);
  function choose(value:ThemePreference) {
    document.cookie = `scentiq-theme=${value}; Path=/; Max-Age=31536000; SameSite=Lax${location.protocol === "https:" ? "; Secure" : ""}`;
    setPreference(value);
  }
  return <ThemeContext value={{preference,setPreference:choose}}>{children}</ThemeContext>;
}

export function AppearanceControl({expanded=false}: {expanded?:boolean}) {
  const {preference,setPreference} = useContext(ThemeContext);
  const id = useId();
  if (expanded) return <fieldset className="appearance-options"><legend className="sr-only">Appearance</legend>{choices.map(({value,label,icon:Icon}) => <label key={value} className="appearance-option" data-selected={preference===value}><input type="radio" name={`appearance-${id}`} value={value} checked={preference===value} onChange={()=>setPreference(value)}/><Icon size={23} aria-hidden="true"/><span>{label}</span></label>)}</fieldset>;
  return <label className="appearance-control"><Sun size={16} aria-hidden="true"/><span className="sr-only">Appearance</span><select value={preference} onChange={event=>setPreference(event.target.value as ThemePreference)}>{choices.map(({value,label})=><option key={value} value={value}>{label}</option>)}</select></label>;
}
