"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";
import { motion } from "motion/react";
import { toast } from "sonner";

import { WearFeedbackDialog } from "@/features/collection/wear-feedback-dialog";
import { CatalogImage } from "@/components/catalog-image";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Carousel } from "@/components/ui/carousel";
import { Dialog, DialogContent } from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { decideRecommendation, wearRecommendation } from "@/lib/server/recommendation-actions";
import { BottleFallback } from "@/features/layering/blend-bottle";
import { bottleSegments } from "@/features/layering/bottle-model";
import { SprayZones } from "@/features/layering/spray-zones";
import type { WearCandidate, WearRecommendation } from "@/types/wear-intelligence";

/** Stable identity for a candidate: a blend shares its anchor's fragrance id. */
export const candidateKey = (candidate: WearCandidate) => `${candidate.fragrance.id}:${candidate.blend_key ?? ""}`;

export function evidenceLabel(value: number): string {
  return value >= 0.75 ? "High evidence" : value >= 0.4 ? "Moderate evidence" : "Limited evidence";
}

export function RecommendationCard(props: {recommendation: WearRecommendation; compact?: boolean}) {
  const router = useRouter();
  const [feedbackWear, setFeedbackWear] = useState<string | null>(null);
  return <>
    {feedbackWear && <WearFeedbackDialog wearId={feedbackWear} onClose={() => {setFeedbackWear(null);router.refresh();}}/>}
    <RecommendationContent key={props.recommendation.id} {...props} onWearLogged={setFeedbackWear}/>
  </>;
}

function RecommendationContent({recommendation, compact = false, onWearLogged}: {recommendation: WearRecommendation; compact?: boolean; onWearLogged: (id: string) => void}) {
  const router = useRouter();
  const initial = [recommendation, ...recommendation.alternatives].find(candidate => recommendation.decision?.selected_fragrance_id != null && candidate.fragrance.id === recommendation.decision.selected_fragrance_id) ?? recommendation;
  const [selected, setSelected] = useState<WearCandidate>(initial);
  const [alternatives, setAlternatives] = useState(false);
  const [details, setDetails] = useState(false);
  const [confirm, setConfirm] = useState(false);
  const [dismissed, setDismissed] = useState(recommendation.decision?.action === "dismissed");
  const [accepted, setAccepted] = useState(recommendation.decision?.action === "accepted");
  const [sprays, setSprays] = useState(initial.recommended_sprays);
  const [occasion, setOccasion] = useState(recommendation.context.occasion ?? "");
  const [setting, setSetting] = useState(recommendation.context.setting ?? "");
  const [note, setNote] = useState("");
  const [pending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const context = recommendation.context;
  const fragrance = selected.fragrance;
  const blend = selected.blend ?? null;
  const title = blend ? blend.items.map(item => item.fragrance.name).join(" + ") : fragrance.name;
  const layerHref = blend
    ? `/layering?stack=${blend.items.map(item => item.fragrance.id).join(",")}&mode=${blend.mode}${blend.goal ? `&goal=${blend.goal}` : ""}`
    : `/layering?a=${fragrance.id}`;
  function choose(candidate: WearCandidate) {
    startTransition(async () => {
      const result = await decideRecommendation(recommendation.id, candidateKey(candidate) === candidateKey(recommendation) ? "accepted" : "replaced", candidate.fragrance.id, candidate.blend_key ?? "");
      if (!result.ok) {setError(result.error); toast.error(result.error); return;}
      setSelected(candidate); setSprays(candidate.recommended_sprays); setDismissed(false); setError(null);
      toast.success("Recommendation updated");
    });
  }
  function decide(action: "accepted" | "dismissed") {
    startTransition(async () => {
      const result = await decideRecommendation(recommendation.id, action, action === "accepted" ? fragrance.id : undefined, action === "accepted" ? selected.blend_key ?? "" : "");
      if (!result.ok) {setError(result.error);toast.error(result.error);return;}
      setDismissed(action === "dismissed"); setAccepted(action === "accepted");
      toast.success(action === "dismissed" ? "Recommendation dismissed" : "Recommendation accepted");
    });
  }
  function logWear() {
    startTransition(async () => {
      const result = await wearRecommendation(recommendation.id, {
        selected_fragrance_id:fragrance.id,blend_key:selected.blend_key ?? "",sprays,notes:note || null,
        occasion: occasion ? occasion as NonNullable<typeof context.occasion> : null, setting:setting || null,
      });
      if (!result.ok) {setError(result.error);toast.error(result.error);return;}
      setConfirm(false);onWearLogged(result.data.id);toast.success("Wear logged");router.refresh();
    });
  }
  if (dismissed) return <Card><CardContent><p>Recommendation dismissed</p><Button variant="ghost" onClick={()=>{setDismissed(false);setAlternatives(true);}}>Explore alternatives</Button></CardContent></Card>;
  return <motion.div layout data-testid="recommendation-card">
    <Card className={compact ? "recommendation-card" : "recommendation-card recommendation-hero"}>
      <CardContent>
        <div className="recommendation-main">
          {blend ? <Link href={layerHref} aria-label={`Open ${title} in the Layering Lab`} className="recommendation-bottle"><BottleFallback segments={bottleSegments(blend)} /></Link> : <Link href={`/collection/${fragrance.id}`} aria-label={`Details for ${fragrance.name}`}>
            <CatalogImage id={fragrance.id} name={fragrance.name} brand={fragrance.brand.name} imageUrl={fragrance.image_url ?? null} className="recommendation-bottle" />
          </Link>}
          <div>
            <p className="eyebrow">{context.occasion ? `${context.occasion} · ${context.daypart}` : "Your open day"}</p>
            <h2 className="serif">{title}</h2><p>{blend ? `Blend of ${blend.items.length} scents` : fragrance.brand.name}</p>
            <div className="recommendation-chips"><Badge>Match {Math.round(selected.score)}%</Badge>{blend && <Badge>Blend score {blend.score_percent}%</Badge>}<Badge>{evidenceLabel(selected.evidence_coverage)}</Badge><Badge>Start with {selected.recommended_sprays} sprays</Badge>{context.high_celsius != null && <Badge>{context.high_celsius}°C · {context.condition ?? "Forecast"}</Badge>}</div>
            <ul>{selected.reasons.slice(0,3).map(reason=><li key={reason}>{reason}</li>)}</ul>
            {selected.warnings.map(warning=><p className="muted" key={warning}>{warning}</p>)}
            {blend && <SprayZones stack={blend} />}
          </div>
        </div>
        <div className="recommendation-actions">
          <Button disabled={pending} onClick={()=>setConfirm(true)}>Wear This</Button>
          <Button disabled={pending || recommendation.alternatives.length === 0} variant="secondary" onClick={()=>setAlternatives(!alternatives)}>Another Option</Button>
          <Button variant="ghost" onClick={()=>setDetails(true)}>Why this?</Button>
          <Button asChild variant="ghost"><Link href={layerHref}>{blend ? "Open Blend" : "Layer It"}</Link></Button>
          {compact && <Button variant="ghost" disabled={pending || accepted} onClick={()=> candidateKey(selected) === candidateKey(recommendation) ? decide("accepted") : choose(selected)}>{accepted ? "Accepted" : "Accept"}</Button>}
          <Button variant="ghost" disabled={pending} onClick={()=>decide("dismissed")}>Dismiss</Button>
        </div>
        {error && <p role="alert">{error}</p>}
        {alternatives && <motion.div layout><Carousel label="Recommendation alternatives">
          {[recommendation,...recommendation.alternatives].map(candidate=>{const name = candidate.blend ? candidate.blend.items.map(item=>item.fragrance.name).join(" + ") : candidate.fragrance.name;return <Card key={candidateKey(candidate)}><CardContent><h3>{name}</h3>{candidate.blend && <Badge>Blend</Badge>}<p>Match {Math.round(candidate.score)}% · {candidate.recommended_sprays} sprays</p><Button disabled={pending} onClick={()=>choose(candidate)}>Choose {name}</Button></CardContent></Card>;})}
        </Carousel></motion.div>}
      </CardContent>
    </Card>
    <Dialog open={details} onOpenChange={setDetails}><DialogContent title={blend ? "Why this blend?" : "Why this fragrance?"}>{blend && <ul>{(blend.pairing_evidence ?? []).map(item => <li key={item}>{item}</li>)}</ul>}<p>Deterministic scores from your collection and context. Evidence coverage measures available inputs, not statistical confidence.</p><dl className="score-breakdown">{Object.entries(selected.score_components).map(([name,value])=><div key={name}><dt>{name.replaceAll("_"," ")}</dt><dd>{value}</dd></div>)}</dl><p>{evidenceLabel(selected.evidence_coverage)} · {recommendation.algorithm_version}</p></DialogContent></Dialog>
    <Dialog open={confirm} onOpenChange={setConfirm}><DialogContent title={`Wear ${title}`}><p>Adjust this starting guidance for your wear.</p>
      <label htmlFor={`sprays-${recommendation.id}`}>Sprays</label><Input id={`sprays-${recommendation.id}`} type="number" min={1} max={30} value={sprays} onChange={event=>setSprays(Number(event.target.value))}/>
      <label htmlFor={`occasion-${recommendation.id}`}>Occasion</label><select id={`occasion-${recommendation.id}`} value={occasion} onChange={event=>setOccasion(event.target.value as typeof occasion)}><option value="">Not specified</option>{["work","casual","date","dinner","party","formal","gym","travel","other"].map(value=><option key={value}>{value}</option>)}</select>
      <label htmlFor={`setting-${recommendation.id}`}>Setting</label><Input id={`setting-${recommendation.id}`} maxLength={40} value={setting} onChange={event=>setSetting(event.target.value)}/>
      <label htmlFor={`note-${recommendation.id}`}>Private note (optional)</label><Input id={`note-${recommendation.id}`} maxLength={2000} value={note} onChange={event=>setNote(event.target.value)}/>
      <Button disabled={pending || !Number.isInteger(sprays) || sprays < 1 || sprays > 30} onClick={logWear}>{pending ? "Saving…" : "Log wear"}</Button><Button variant="ghost" onClick={()=>setConfirm(false)}>Cancel</Button>
    </DialogContent></Dialog>
  </motion.div>;
}
