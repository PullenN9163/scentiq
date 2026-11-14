"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { readAgentStream, type AgentCard } from "@/features/agent/stream";

export type AskTurn = {
  id: string;
  role: "user" | "assistant";
  /** What the member sees. */
  text: string;
  /** What was sent, when it differs from `text` (a context prefix). */
  sent?: string;
  cards: AgentCard[];
  fallback?: string;
  error?: string;
};

export type AskContext = { fragranceId: string; name: string; brand: string };

/** "About Another 13 by Le Labo: " */
export function contextPrefix(context: AskContext): string {
  return `About ${context.name} by ${context.brand}: `;
}

/**
 * The advisor conversation. The request and stream handling are the same as
 * the existing AgentExperience: POST /api/agent/chat with { message, history },
 * history the last 8 turns, each cut to 2000 characters, read with
 * readAgentStream.
 */
export function useConversation(authenticated = true) {
  const [turns, setTurns] = useState<AskTurn[]>([]);
  const [streaming, setStreaming] = useState(false);
  const [status, setStatus] = useState("");
  const [announcement, setAnnouncement] = useState("");
  const controller = useRef<AbortController | null>(null);
  const turnsRef = useRef<AskTurn[]>([]);
  useEffect(() => { turnsRef.current = turns; }, [turns]);

  useEffect(() => () => { controller.current?.abort(); }, []);

  const ask = useCallback(async (question: string, prefix = "") => {
    const shown = question.trim();
    const message = `${prefix}${shown}`;
    if (!authenticated || !shown || message.length > 2000 || controller.current) return;
    const active = new AbortController();
    controller.current = active;
    const id = crypto.randomUUID();
    const history = turnsRef.current
      .filter((turn) => turn.text && !turn.error)
      .slice(-8)
      .map((turn) => ({ role: turn.role, content: (turn.sent ?? turn.text).slice(0, 2000) }));
    while (history.reduce((total, turn) => total + turn.content.length, message.length) > 12000) history.shift();
    setTurns((items) => [
      ...items.slice(-30),
      { id: crypto.randomUUID(), role: "user", text: shown, sent: prefix ? message : undefined, cards: [] },
      { id, role: "assistant", text: "", cards: [] },
    ]);
    setStreaming(true);
    setStatus("Checking your ScentIQ context…");
    setAnnouncement("ScentIQ is preparing your answer.");
    const update = (change: (turn: AskTurn) => AskTurn) => setTurns((items) => items.map((turn) => (turn.id === id ? change(turn) : turn)));
    try {
      const response = await fetch("/api/agent/chat", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ message, history }), signal: active.signal });
      if (!response.ok || !response.body) throw new Error(response.status === 401 ? "Your session expired. Sign in again to continue." : "The advisor could not complete your request. Please try again.");
      for await (const event of readAgentStream(response.body)) {
        if (event.type === "text_delta") update((turn) => ({ ...turn, text: turn.text + event.delta }));
        else if (event.type === "card") update((turn) => ({ ...turn, cards: [...turn.cards, event.card] }));
        else if (event.type === "fallback") { update((turn) => ({ ...turn, fallback: event.label })); if (event.label) setStatus(event.label); }
        else if (event.type === "done") { setAnnouncement("ScentIQ's answer is ready."); setStatus(""); }
        else setStatus(event.label ?? "Checking your context…");
      }
    } catch (error) {
      const stopped = active.signal.aborted;
      update((turn) => ({ ...turn, error: stopped ? "Response stopped." : error instanceof Error ? error.message : "The advisor is unavailable." }));
      setAnnouncement(stopped ? "Response stopped." : "The advisor request failed.");
    } finally {
      controller.current = null;
      setStreaming(false);
      setStatus("");
    }
  }, [authenticated]);

  const stop = useCallback(() => controller.current?.abort(), []);

  /** Ask the last question again after an error. */
  const retry = useCallback(() => {
    const items = turnsRef.current;
    const lastUser = [...items].reverse().find((turn) => turn.role === "user");
    if (!lastUser) return;
    const prefix = lastUser.sent ? lastUser.sent.slice(0, lastUser.sent.length - lastUser.text.length) : "";
    void ask(lastUser.text, prefix);
  }, [ask]);

  return { turns, streaming, status, announcement, ask, stop, retry, authenticated };
}

export type Conversation = ReturnType<typeof useConversation>;
