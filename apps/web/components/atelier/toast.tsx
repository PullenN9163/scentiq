"use client";

import { Toaster } from "sonner";

import styles from "./toast.module.css";

/**
 * Sonner styled for Atelier: bottom right on desktop, bottom center on
 * phones, on surface with shadow-float, a success mark beside the words.
 */
export function AtelierToaster() {
  return (
    <Toaster
      position="bottom-right"
      offset={{ bottom: 24, right: 24 }}
      mobileOffset={{ bottom: "calc(96px + env(safe-area-inset-bottom))" }}
      toastOptions={{
        unstyled: true,
        classNames: {
          toast: styles.toast,
          title: styles.title,
          description: styles.description,
          success: styles.success,
          error: styles.error,
          actionButton: styles.action,
          cancelButton: styles.action,
          closeButton: styles.close,
          icon: styles.icon,
        },
      }}
    />
  );
}
