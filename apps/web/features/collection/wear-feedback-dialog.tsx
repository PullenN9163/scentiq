"use client";
import { useActionState, useEffect, useState } from "react";
import { toast } from "sonner";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Field, FormMessage } from "@/components/shared/form-field";
import { getWearFeedback, saveWearFeedback } from "@/lib/server/feedback-actions";
import { idleState } from "@/lib/action-state";

export function WearFeedbackDialog({ wearId, onClose }: { wearId: string; onClose: () => void }) {
  const [previous, setPrevious] = useState<Awaited<ReturnType<typeof getWearFeedback>>>(null);
  const [loading, setLoading] = useState(true);
  const [loadFailed, setLoadFailed] = useState(false);
  const [state, action, pending] = useActionState(async (prev: typeof idleState, form: FormData) => { const result = await saveWearFeedback(prev, form); if (result.status === "success") { toast.success(result.message); onClose(); } return result; }, idleState);
  useEffect(() => { let active = true; void getWearFeedback(wearId).then((value) => { if (active) setPrevious(value); }).catch(() => { if (active) setLoadFailed(true); }).finally(() => { if (active) setLoading(false); }); return () => { active = false; }; }, [wearId]);
  return <Dialog open onOpenChange={(open) => { if (!open) onClose(); }}><DialogContent title="How did it wear?">{loading ? <p role="status">Loading feedback…</p> : loadFailed ? <p role="alert">Your feedback could not be loaded. Close and try again.</p> : <form action={action} className="form-grid"><FormMessage state={state} /><input type="hidden" name="wear_log_id" value={wearId} /><Field name="rating" label="Rating (1–5)" state={state} fallbackValue={previous?.rating?.toString() ?? ""}>{(props) => <Input type="number" min={1} max={5} step={1} {...props} />}</Field><Field name="longevity" label="Longevity (0–10)" state={state} fallbackValue={previous?.longevity?.toString() ?? ""}>{(props) => <Input type="number" min={0} max={10} step="0.1" {...props} />}</Field><Field name="projection" label="Projection" state={state} fallbackValue={previous?.projection ?? ""}>{(props) => <select className="select" {...props}><option value="">Not recorded</option><option value="intimate">Intimate</option><option value="moderate">Moderate</option><option value="strong">Strong</option></select>}</Field><div className="field--full"><Field name="comments" label="Comments" state={state} fallbackValue={previous?.comments ?? ""}>{(props) => <textarea className="textarea" rows={3} maxLength={2000} {...props} />}</Field></div><Button disabled={pending}>{pending ? "Saving…" : "Save feedback"}</Button></form>}</DialogContent></Dialog>;
}
