import { SignUp } from "@clerk/nextjs";
import Link from "next/link";
import { AppearanceControl } from "@/components/ui/theme-provider";

/**
 * Sign-up exists for invited people completing enrolment. Clerk refuses anyone
 * without an invitation, so this page does not gate anything itself.
 */
export default function SignUpPage() {
  return (
    <main className="auth-page">
      <nav className="auth-nav" aria-label="Account navigation"><Link href="/" className="brand"><span className="brand__mark">S</span>ScentIQ</Link><AppearanceControl /></nav>
      <div><div className="auth-welcome"><p className="eyebrow">Private beta</p><h1>Make room for discovery.</h1><p className="muted">Your collection. Your rhythm. Your ScentIQ.</p></div><SignUp /></div>
    </main>
  );
}
