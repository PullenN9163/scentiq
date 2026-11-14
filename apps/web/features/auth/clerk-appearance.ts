import styles from "./auth.module.css";

/**
 * Clerk appearance for the Atelier interface. Colors reference the Atelier
 * tokens so the hosted form follows the page's theme. Applied in the root
 * layout only when the Atelier flag is on.
 */
export const atelierClerkAppearance = {
  variables: {
    colorPrimary: "var(--action)",
    colorTextOnPrimaryBackground: "var(--on-action)",
    colorBackground: "var(--surface)",
    colorText: "var(--ink)",
    colorTextSecondary: "var(--ink-muted)",
    colorInputBackground: "var(--surface-sunken)",
    colorInputText: "var(--ink)",
    colorNeutral: "var(--ink)",
    borderRadius: "0.875rem",
    fontFamily: "var(--font-sans)",
  },
  elements: {
    card: styles.clerkCard,
    headerTitle: styles.clerkHidden,
    headerSubtitle: styles.clerkHidden,
    formButtonPrimary: styles.clerkPrimary,
    socialButtonsBlockButton: styles.clerkSocial,
    socialButtonsProviderIcon__apple: styles.clerkAppleIcon,
    formFieldInput: styles.clerkInput,
    dividerLine: styles.clerkDivider,
    footer: styles.clerkFooter,
    footerActionLink: styles.clerkLink,
  },
};
