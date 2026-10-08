"use client";

import { Send, Sparkles, Square } from "lucide-react";
import { useEffect, useRef, useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Button } from "@/components/ui/button";
import { AgentResultCard } from "./result-card";
import { readAgentStream, type AgentCard } from "./stream";
import "./agent.css";

const prompts = [
  ["Wear today", "What should I wear today?"],
  ["Plan my week", "Plan my week"],
  ["Date night", "What should I wear to dinner tonight?"],
  ["Neglected bottles", "Which fragrances am I neglecting?"],
  ["Layer this fragrance", "Help me choose an owned anchor fragrance to layer"],
  ["Build a 3-scent stack", "Build me a three-fragrance layering stack"],
  ["What should I buy next?", "What should I buy next?"],
] as const;

type Message = { id: string; role: "user" | "assistant"; text: string; cards: AgentCard[]; fallback?: string; error?: string };

export function AgentExperience({ authenticated }: { authenticated: boolean }) {
  const [messages, setMessages] = useState<Message[]>([]);
  const [draft, setDraft] = useState("");
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const controller = useRef<AbortController | null>(null);
  const last = useRef<HTMLDivElement>(null);
  const composer = useRef<HTMLTextAreaElement>(null);

  useEffect(() => () => { controller.current?.abort(); }, []);
  useEffect(() => { last.current?.scrollIntoView?.({ block: "nearest" }); }, [messages.length, streaming]);

  async function ask(question: string) {
    const message = question.trim();
    if (!authenticated || streaming || !message || message.length > 2000 || controller.current) return;
    const active = new AbortController();
    controller.current = active;
    const id = crypto.randomUUID();
    const history = messages.filter((turn) => turn.text && !turn.error).slice(-8).map((turn) => ({ role: turn.role, content: turn.text.slice(0, 2000) }));
    while (history.reduce((total, turn) => total + turn.content.length, message.length) > 12000) history.shift();
    setMessages((items) => [...items.slice(-30), { id: crypto.randomUUID(), role: "user", text: message, cards: [] }, { id, role: "assistant", text: "", cards: [] }]);
    setDraft(""); setStreaming(true); setStatus("Checking your ScentIQ context…"); setAnnouncement("ScentIQ is preparing your answer.");
    function update(change: (turn: Message) => Message) { setMessages((items) => items.map((turn) => turn.id === id ? change(turn) : turn)); }
    try {
      const response = await fetch("/api/agent/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message, history }), signal: active.signal });
      if (!response.ok || !response.body) throw new Error(response.status === 401 ? "Your session expired. Sign in again to continue." : "The advisor could not complete your request. Please try again.");
      for await (const event of readAgentStream(response.body)) {
        if (event.type === "text_delta") update((turn) => ({ ...turn, text: turn.text + event.delta }));
        else if (event.type === "card") update((turn) => ({ ...turn, cards: [...turn.cards, event.card] }));
        else if (event.type === "fallback") update((turn) => ({ ...turn, fallback: event.label }));
        else if (event.type === "done") { setAnnouncement("ScentIQ's answer is ready."); setStatus(""); }
        else setStatus(event.label ?? "Checking your context…");
      }
    } catch (error) {
      const stopped = active.signal.aborted;
      update((turn) => ({ ...turn, error: stopped ? "Response stopped." : error instanceof Error ? error.message : "The advisor is unavailable." }));
      setAnnouncement(stopped ? "Response stopped." : "The advisor request failed.");
    } finally {
      controller.current = null; setStreaming(false); setStatus(""); composer.current?.focus();
    }
  }

  return (
    <section className="page agent-page">
      <PageHeader eyebrow="Your fragrance advisor" title="Ask ScentIQ" description="Choose what to wear, explore your collection, or build a thoughtful layering stack." />
      <p className="muted">Recommendations come from your collection and ScentIQ’s scoring. Your conversation stays in this session.</p>
      <div className="agent-shell">
        <div className="conversation" role="region" aria-label="Fragrance conversation" aria-busy={streaming}>
          {messages.length === 0 && <div className="agent-welcome"><Sparkles aria-hidden="true" /><h2 className="serif">What would you like to decide?</h2><p>Start with today’s plans or an overlooked bottle.</p></div>}
          {messages.map((turn) => <article key={turn.id} className={turn.role === "user" ? "agent-user-message" : "agent-bubble"} aria-label={turn.role === "user" ? "Your question" : "ScentIQ answer"}>
            {turn.fallback && <p className="agent-fallback"><small>{turn.fallback}</small></p>}
            {turn.text && <p className="agent-answer-text">{turn.text}</p>}
            {turn.cards.map((card, index) => <AgentResultCard key={index} card={card} />)}
            {turn.error && <p role="alert">{turn.error}</p>}
          </article>)}
          {status && <p className="agent-status">{status}</p>}
          <div ref={last} />
        </div>
        <div className="quick-prompts" aria-label="Suggested questions">{prompts.map(([label, text]) => <button key={label} disabled={!authenticated || streaming} onClick={() => void ask(text)}>{label}</button>)}</div>
        <form className="agent-composer" onSubmit={(event) => { event.preventDefault(); void ask(draft); }}>
          <label htmlFor="advisor-question" className="sr-only">Ask your fragrance advisor</label>
          <textarea ref={composer} id="advisor-question" rows={2} maxLength={2000} value={draft} disabled={!authenticated || streaming} placeholder={authenticated ? "What should I wear to dinner tonight?" : "Sign in to ask ScentIQ"} onChange={(event) => setDraft(event.target.value)} onKeyDown={(event) => { if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); void ask(draft); } }} />
          {streaming ? <Button type="button" variant="secondary" onClick={() => controller.current?.abort()}><Square size={16} aria-hidden="true" /> Stop</Button> : <Button type="submit" disabled={!authenticated || !draft.trim()}><Send size={16} aria-hidden="true" /> Send</Button>}
          <small className="muted">Enter to send · Shift+Enter for a new line</small>
        </form>
      </div>
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{announcement}</div>
    </section>
  );
}
