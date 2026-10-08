import { SignIn } from "@clerk/nextjs";

/**
 * Invite-only sign-in. Enrolment is controlled in Clerk (invitations or an
 * allowlist), so this page only renders the provider's own flow.
 */
export default function SignInPage() {
  return (
    <main className="auth-page">
      <SignIn />
    </main>
  );
}
