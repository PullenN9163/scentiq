import { clerkMiddleware, createRouteMatcher } from "@clerk/nextjs/server";

/**
 * Everything in the app shell requires a session. The landing page, the Clerk
 * webhook and the status probe stay public; the webhook authenticates with a
 * provider signature rather than a session, and would break if it were
 * redirected to sign-in.
 */
const isPublicRoute = createRouteMatcher([
  "/",
  "/sign-in(.*)",
  "/sign-up(.*)",
  "/api/webhooks/clerk",
  "/api/status",
]);

// Next 16 renamed the `middleware` file convention to `proxy`; the exported
// function name must match the convention.
export const proxy = clerkMiddleware(async (auth, request) => {
  if (!isPublicRoute(request)) {
    await auth.protect();
  }
});

export const config = {
  matcher: [
    // Skip Next internals and static files unless they appear in search params.
    "/((?!_next|[^?]*\\.(?:html?|css|js(?!on)|jpe?g|webp|png|gif|svg|ttf|woff2?|ico|csv|docx?|xlsx?|zip|webmanifest)).*)",
    "/(api|trpc)(.*)",
  ],
};
