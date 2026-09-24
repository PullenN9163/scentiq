"use client";

import { ArrowRight, Send, Sparkles } from "lucide-react";
import Link from "next/link";
import { FormEvent, useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { PreviewNotice } from "@/components/shared/states";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { getDemoFragranceById, getDemoInsights, getDemoLayeringSuggestions, getDemoToday, getDemoWeek } from "@/lib/demo";

const prompts = ["What should I wear today?", "What should I wear tomorrow?", "What should I wear to work?", "What should I wear on my date?", "What should I buy next?", "What am I missing for winter?", "Which fragrances am I neglecting?", "Give me a layering combo.", "What are my most worn fragrances?", "What is my collection worth?"];

function answerFor(prompt: string) {
  const today = getDemoToday(); const week = getDemoWeek(); const insights = getDemoInsights(); const layer = getDemoLayeringSuggestions()[0];
  const answers: Record<string, { text: string; href: string; link: string }> = {
    [prompts[0]]: { text: `${getDemoFragranceById(today.recommendation.primary.fragranceId)!.name} is today’s strongest match at ${today.recommendation.primary.score}%. It suits the clear-after-rain forecast and moves easily from your studio review into dinner.`, href: "/dashboard", link: "Open Today" },
    [prompts[1]]: { text: `${getDemoFragranceById(week[1].primary.fragranceId)!.name} is planned for tomorrow with ${week[1].primary.sprays} sprays.`, href: "/week", link: "Open the week" },
    [prompts[2]]: { text: "Cedar After Rain and Paper Musk are your best quiet office choices in this demo rotation.", href: "/collection/cedar-after-rain", link: "View Cedar After Rain" },
    [prompts[3]]: { text: "Amber Index fits the cooler evening and has enough warmth for a date without becoming overly sweet.", href: "/collection/amber-index", link: "View Amber Index" },
    [prompts[4]]: { text: "Mint Condition adds a crisp gym-and-travel role at a low overlap with your current wardrobe.", href: "/discover", link: "Open Discover" },
    [prompts[5]]: { text: "Warm-weather formality is the clearest use-case gap; consider a polished citrus or airy floral before another clean woody office scent.", href: "/insights", link: "See coverage" },
    [prompts[6]]: { text: `${getDemoFragranceById(insights.leastWornId)!.name} has the fewest demo wears. Try it for your next evening plan.`, href: `/collection/${insights.leastWornId}`, link: "View fragrance" },
    [prompts[7]]: { text: `${getDemoFragranceById(layer.fragranceAId)!.name} + ${getDemoFragranceById(layer.fragranceBId)!.name} is a ${layer.score}% demo match.`, href: `/layering?a=${layer.fragranceAId}`, link: "Open Layering Lab" },
    [prompts[8]]: { text: `${getDemoFragranceById(insights.mostWornId)!.name} leads your demo wear history.`, href: "/insights", link: "See wear insights" },
    [prompts[9]]: { text: `Your demo collection represents $${insights.totalCost.toLocaleString()} in recorded purchase cost. This is not a resale valuation.`, href: "/insights", link: "Open Insights" },
  };
  return answers[prompt] ?? { text: "This demo currently supports the quick intents shown below. Freeform understanding and LLM calls are intentionally not enabled.", href: "/agent", link: "View supported prompts" };
}

export function AgentExperience() {
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<{ prompt: string; answer: ReturnType<typeof answerFor> }[]>([]);
  const ask = (prompt: string) => { setMessages((items) => [...items, { prompt, answer: answerFor(prompt) }]); setInput(""); };
  const submit = (event: FormEvent) => { event.preventDefault(); if (input.trim()) ask(input.trim()); };
  return <section className="page agent-page"><PageHeader eyebrow="Deterministic demo advisor" title="Ask ScentIQ" description="Fast answers grounded in the same demo collection—without pretending to understand arbitrary prompts." /><PreviewNotice>The advisor is a preview that answers from sample data. It cannot see your collection and saves nothing.</PreviewNotice><div className="agent-shell"><div className="conversation" aria-live="polite">{messages.length === 0 && <div className="agent-welcome"><span><Sparkles /></span><h2 className="serif">What would you like to decide?</h2><p>Choose a supported intent to see how a future fragrance advisor could use your context.</p></div>}{messages.map((message, index) => <div className="exchange" key={`${message.prompt}-${index}`}><p className="user-bubble">{message.prompt}</p><div className="agent-bubble"><Badge>Demo response</Badge><p>{message.answer.text}</p><Link href={message.answer.href}>{message.answer.link} <ArrowRight size={15} /></Link></div></div>)}</div><div className="quick-prompts">{prompts.map((prompt) => <button key={prompt} onClick={() => ask(prompt)}>{prompt}</button>)}</div><form className="agent-input" onSubmit={submit}><label className="sr-only" htmlFor="agent-question">Ask ScentIQ</label><input id="agent-question" value={input} onChange={(event) => setInput(event.target.value)} placeholder="Try a supported question…" /><Button type="submit"><Send size={16} />Send</Button></form></div></section>;
}
