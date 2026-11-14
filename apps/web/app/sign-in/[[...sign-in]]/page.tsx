import { SignIn } from "@clerk/nextjs";
import Link from "next/link";
import { AppearanceControl } from "@/components/ui/theme-provider";
import { AtelierAuthFrame } from "@/features/auth/atelier-auth-frame";
import { isAtelierEnabled } from "@/lib/atelier-flag";

/**
 * Invite-only sign-in. Enrolment is controlled in Clerk (invitations or an
 * allowlist), so this page only renders the provider's own flow.
 */
export default function SignInPage() {
  if (isAtelierEnabled()) return <AtelierAuthFrame mode="sign-in"><SignIn /></AtelierAuthFrame>;
  return (
    <main className="auth-page">
      <nav className="auth-nav" aria-label="Account navigation"><Link href="/" className="brand"><span className="brand__mark">S</span>ScentIQ</Link><AppearanceControl /></nav>
      <div><div className="auth-welcome"><p className="eyebrow">Your fragrance wardrobe</p><h1>Welcome back.</h1><p className="muted">A more considered scent, every day.</p></div><SignIn /></div>
    </main>
  );
}
