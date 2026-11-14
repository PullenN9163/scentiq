"use client";

import * as DialogPrimitive from "@radix-ui/react-dialog";
import { X } from "lucide-react";
import { animate, motion, useDragControls, useMotionValue, type PanInfo } from "motion/react";
import { useEffect, useRef, useState, type CSSProperties, type ReactNode } from "react";

import { motionTokens } from "@/lib/motion";
import { cn } from "@/lib/utils";

import styles from "./sheet.module.css";

/** Below this width the sheet rises from the bottom and can be dragged away. */
const DRAG_QUERY = "(max-width: 1099px)";

function useDragEnabled(): boolean {
  const [enabled, setEnabled] = useState(false);
  useEffect(() => {
    if (typeof window === "undefined" || !window.matchMedia) return;
    const query = window.matchMedia(DRAG_QUERY);
    const update = () => setEnabled(query.matches);
    update();
    query.addEventListener?.("change", update);
    return () => query.removeEventListener?.("change", update);
  }, []);
  return enabled;
}

export type SheetProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  title: string;
  /** Keep the title for screen readers only, when the content has its own heading. */
  hideTitle?: boolean;
  description?: string;
  /** Controls placed in the header beside the close button. */
  toolbar?: ReactNode;
  /** Pinned to the bottom of the sheet (actions on phones). */
  footer?: ReactNode;
  children: ReactNode;
  /** Right panel width at 1100px and up. Defaults to 460px. */
  panelWidth?: number;
  className?: string;
  /** Override the nested theme, e.g. "dark" inside the Blend studio. */
  theme?: "light" | "dark";
};

/**
 * The one sheet: a right panel at 1100px and up, a centered 560px bottom
 * sheet from 700 to 1099px, and a full-width bottom sheet at 92% height under
 * 700px. Built on Radix dialog, so it traps focus, closes on Escape and
 * returns focus to whatever opened it.
 */
export function Sheet({
  open,
  onOpenChange,
  title,
  hideTitle = false,
  description,
  toolbar,
  footer,
  children,
  panelWidth = 460,
  className,
  theme,
}: SheetProps) {
  return (
    <DialogPrimitive.Root open={open} onOpenChange={onOpenChange}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className={styles.scrim} data-theme={theme} />
        <SheetSurface
          title={title}
          hideTitle={hideTitle}
          description={description}
          toolbar={toolbar}
          footer={footer}
          panelWidth={panelWidth}
          className={className}
          theme={theme}
          onDismiss={() => onOpenChange(false)}
        >
          {children}
        </SheetSurface>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}

function SheetSurface({
  title,
  hideTitle,
  description,
  toolbar,
  footer,
  children,
  panelWidth,
  className,
  theme,
  onDismiss,
}: Omit<SheetProps, "open" | "onOpenChange"> & { onDismiss: () => void }) {
  // Captured when the portal mounts, before Radix moves focus into the sheet,
  // so controlled sheets opened without a Trigger still restore focus.
  const opener = useRef(typeof document === "undefined" ? null : document.activeElement);
  const panel = useRef<HTMLDivElement>(null);
  const dragEnabled = useDragEnabled();
  const controls = useDragControls();
  const y = useMotionValue(0);

  function endDrag(_: unknown, info: PanInfo) {
    const height = panel.current?.offsetHeight ?? 600;
    if (info.offset.y > height * 0.3 || info.velocity.y > 700) {
      void animate(y, height, { duration: 0.18, ease: "easeIn" }).then(onDismiss);
    } else {
      void animate(y, 0, motionTokens.springSoft);
    }
  }

  return (
    <DialogPrimitive.Content
      className={cn(styles.content, className)}
      style={{ "--panel-width": `${panelWidth}px` } as CSSProperties}
      data-theme={theme}
      onCloseAutoFocus={(event) => {
        if (opener.current instanceof HTMLElement && opener.current.isConnected) {
          event.preventDefault();
          opener.current.focus();
        }
      }}
    >
      <motion.div
        ref={panel}
        className={styles.panel}
        style={{ y }}
        drag={dragEnabled ? "y" : false}
        dragListener={false}
        dragControls={controls}
        dragConstraints={{ top: 0 }}
        dragElastic={{ top: 0, bottom: 0.9 }}
        dragMomentum={false}
        onDragEnd={endDrag}
      >
        <div
          className={styles.handleArea}
          onPointerDown={(event) => { if (dragEnabled) controls.start(event); }}
          aria-hidden="true"
        >
          <span className={styles.handle} />
        </div>
        <div className={styles.header}>
          <DialogPrimitive.Title className={cn("at-subtitle", styles.title, hideTitle && "sr-only")}>{title}</DialogPrimitive.Title>
          <div className={styles.toolbar}>
            {toolbar}
            <DialogPrimitive.Close className={styles.close} aria-label={`Close ${title}`}>
              <X aria-hidden="true" />
            </DialogPrimitive.Close>
          </div>
        </div>
        {description ? (
          <DialogPrimitive.Description className={cn("at-caption", styles.description)}>{description}</DialogPrimitive.Description>
        ) : (
          <DialogPrimitive.Description className="sr-only">{title}</DialogPrimitive.Description>
        )}
        <div className={styles.body}>{children}</div>
        {footer ? <div className={styles.footer}>{footer}</div> : null}
      </motion.div>
    </DialogPrimitive.Content>
  );
}

export const SheetClose = DialogPrimitive.Close;
