/**
 * The shape every form Server Action returns.
 *
 * This lives outside `lib/server/actions.ts` because a `"use server"` module may
 * only export async functions — a plain constant or type exported from there is
 * a build error. Client Components import the type and the initial value here.
 */

export type ActionState = {
  status: "idle" | "success" | "error";
  message?: string;
  fieldErrors?: Record<string, string>;
  /**
   * What the user submitted, echoed back so a failed form re-renders with the
   * input still in place rather than blanking it.
   */
  values?: Record<string, string>;
};

export const idleState: ActionState = { status: "idle" };
