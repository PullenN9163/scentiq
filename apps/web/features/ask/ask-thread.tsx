"use client";

import { ArrowUp, Square, X } from "lucide-react";
import { motion } from "motion/react";
import { useEffect, useRef, useState } from "react";

import { Button } from "@/components/atelier/button";
import { Chip } from "@/components/atelier/chip";
import { motionTokens } from "@/lib/motion";
import { cn } from "@/lib/utils";

import { AskResult } from "./ask-results";
import { contextPrefix, type AskContext, type Conversation as ConversationState } from "./use-ask-thread";
import styles from "./ask.module.css";

export const QUICK_PROMPTS: [label: string, question: string][] = [
  ["Wear today", "What should I wear today?"],
  ["Plan my week", "Plan my week"],
  ["What am I neglecting?", "Which fragrances am I neglecting?"],
  ["Layer this", "Help me choose an owned anchor fragrance to layer"],
  ["What should I buy next?", "What should I buy next?"],
];

/**
 * The Ask conversation: user turns as right-aligned bubbles, the assistant
 * as plain text and result cards, one quiet status line while it works.
 */
export function Conversation({
  conversation,
  context,
  onClearContext,
  autoFocus = false,
  layout = "panel",
}: {
  conversation: ConversationState;
  context?: AskContext | null;
  onClearContext?: () => void;
  autoFocus?: boolean;
  layout?: "panel" | "page";
}) {
  const { turns, streaming, status, announcement, ask, stop, retry, authenticated } = conversation;
  const [draft, setDraft] = useState("");
  const composer = useRef<HTMLTextAreaElement>(null);
  const end = useRef<HTMLDivElement>(null);
  const empty = turns.length === 0;

  useEffect(() => { end.current?.scrollIntoView?.({ block: "nearest" }); }, [turns.length, streaming]);
  useEffect(() => { if (autoFocus) composer.current?.focus(); }, [autoFocus]);

  function send(question: string) {
    if (!question.trim() || streaming) return;
    // The fragrance context prefixes the first message sent with it, then clears.
    const prefix = context ? contextPrefix(context) : "";
    setDraft("");
    void ask(question, prefix).then(() => composer.current?.focus());
    if (context) onClearContext?.();
  }

  const lastAssistant = [...turns].reverse().find((turn) => turn.role === "assistant");

  return (
    <div className={cn(styles.conversation, layout === "page" && styles.pageLayout)}>
      <div className={styles.thread} role="region" aria-label="Conversation with Ask" aria-busy={streaming}>
        {empty ? (
          <div className={styles.empty}>
            <h2 className="at-title">What should we decide?</h2>
            <div className={styles.prompts} aria-label="Suggested questions">
              {QUICK_PROMPTS.map(([label, question]) => (
                <Chip key={label} variant="choice" pressed={false} disabled={!authenticated || streaming} onClick={() => send(question)}>{label}</Chip>
              ))}
            </div>
            <p className="at-caption">Your conversation stays in this session.</p>
          </div>
        ) : null}
        {turns.map((turn) => (
          <article key={turn.id} className={turn.role === "user" ? styles.user : styles.assistant} aria-label={turn.role === "user" ? "Your question" : "Ask's answer"}>
            {turn.text ? <p className={turn.role === "user" ? styles.userText : cn("at-body", styles.answer)}>{turn.text}</p> : null}
            {turn.cards.map((card, index) => (
              <motion.div key={index} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} transition={motionTokens.quick}>
                <AskResult card={card} />
              </motion.div>
            ))}
            {turn.error ? (
              <p className={styles.error} role="alert">
                {turn.error}
                {turn === lastAssistant && !streaming ? <Button size="sm" variant="text" onClick={retry}>Try again</Button> : null}
              </p>
            ) : null}
          </article>
        ))}
        {status ? <p className={styles.status}><i aria-hidden="true" />{status}</p> : null}
        <div ref={end} />
      </div>
      <form className={styles.composer} onSubmit={(event) => { event.preventDefault(); send(draft); }}>
        {context ? (
          <span className={styles.context}>
            <Chip>About {context.name}</Chip>
            {onClearContext ? <button type="button" className={styles.clearContext} aria-label={`Stop asking about ${context.name}`} onClick={onClearContext}><X aria-hidden="true" /></button> : null}
          </span>
        ) : null}
        <div className={styles.field}>
          <label htmlFor="ask-question" className="sr-only">Ask about your collection</label>
          <textarea
            ref={composer}
            id="ask-question"
            rows={1}
            maxLength={2000}
            value={draft}
            disabled={!authenticated}
            placeholder={authenticated ? "Ask about your collection" : "Sign in to ask ScentIQ"}
            onChange={(event) => setDraft(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && !event.shiftKey && !event.nativeEvent.isComposing) { event.preventDefault(); send(draft); }
            }}
          />
          {streaming ? (
            <button type="button" className={styles.send} aria-label="Stop" onClick={stop}><Square aria-hidden="true" /></button>
          ) : (
            <button type="submit" className={styles.send} aria-label="Send" disabled={!authenticated || !draft.trim()}><ArrowUp aria-hidden="true" /></button>
          )}
        </div>
      </form>
      <div className="sr-only" role="status" aria-live="polite" aria-atomic="true">{announcement}</div>
    </div>
  );
}
