import { SignUp } from "@clerk/nextjs";

/**
 * Sign-up exists for invited people completing enrolment. Clerk refuses anyone
 * without an invitation, so this page does not gate anything itself.
 */
export default function SignUpPage() {
  return (
    <main className="auth-page">
      <SignUp />
    </main>
  );
}
