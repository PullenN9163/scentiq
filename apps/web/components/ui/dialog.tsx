"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { useRef, type ReactNode } from "react";

export function Dialog({ open, onOpenChange, children }: { open: boolean; onOpenChange: (open: boolean) => void; children: ReactNode }) {
  return <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>{children}</DialogPrimitive.Root>;
}

type ContentProps = { title: string; eyebrow?: string; children: ReactNode; className?: string; responsive?: boolean };

function DialogSurface({ title, eyebrow, children, className = "", responsive = true }: ContentProps) {
  // Captured when the portal mounts, before Radix moves focus into the panel.
  // This also restores focus for controlled dialogs opened without a Trigger.
  const opener = useRef(typeof document === "undefined" ? null : document.activeElement);
  return <DialogPrimitive.Content className={`modal ${responsive ? "modal--responsive" : ""} ${className}`} aria-describedby={undefined} onCloseAutoFocus={(event) => { if (opener.current instanceof HTMLElement && opener.current.isConnected) { event.preventDefault(); opener.current.focus(); } }}>
    <div className="modal__header"><div>{eyebrow && <p className="eyebrow">{eyebrow}</p>}<DialogPrimitive.Title className="serif">{title}</DialogPrimitive.Title></div><DialogPrimitive.Close aria-label={`Close ${title}`}><X /></DialogPrimitive.Close></div>{children}
  </DialogPrimitive.Content>;
}

export function DialogContent(props: ContentProps) {
  return (
    <DialogPrimitive.Portal>
      <DialogPrimitive.Overlay className="modal-backdrop" />
      <DialogSurface {...props} />
    </DialogPrimitive.Portal>
  );
}

export const DialogTrigger = DialogPrimitive.Trigger;
export const DialogClose = DialogPrimitive.Close;
