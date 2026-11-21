"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { Sheet } from "@/components/atelier/sheet";

import { Conversation } from "./ask-thread";
import { useConversation, type AskContext, type Conversation as ConversationState } from "./use-ask-thread";

type AskApi = {
  open: (context?: AskContext | null) => void;
  conversation: ConversationState;
};

const AskContextValue = createContext<AskApi | null>(null);

/** Open the Ask panel, optionally about one fragrance. */
export function useAsk(): AskApi["open"] {
  const value = useContext(AskContextValue);
  return value?.open ?? (() => window.dispatchEvent(new Event("scentiq:command")));
}

/** The shared conversation (the /agent page uses the same one as the panel). */
export function useAskConversation(): ConversationState | null {
  return useContext(AskContextValue)?.conversation ?? null;
}

/**
 * Ask everywhere: a right panel (440px) at 1100px and up, a centered sheet on
 * iPad portrait and a bottom sheet on phones. The conversation lives here, so
 * it survives closing the panel within the session. Ctrl/⌘ K and the
 * scentiq:command event open it.
 */
export function AskProvider({ children }: { children: ReactNode }) {
  const conversation = useConversation(true);
  const [open, setOpen] = useState(false);
  const [context, setContext] = useState<AskContext | null>(null);

  const show = useCallback((next?: AskContext | null) => {
    setContext(next ?? null);
    setOpen(true);
  }, []);

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        setOpen((value) => !value);
      }
    };
    const onCommand = () => show(null);
    window.addEventListener("keydown", onKey);
    window.addEventListener("scentiq:command", onCommand);
    return () => { window.removeEventListener("keydown", onKey); window.removeEventListener("scentiq:command", onCommand); };
  }, [show]);

  const api = useMemo(() => ({ open: show, conversation }), [show, conversation]);

  return (
    <AskContextValue value={api}>
      {children}
      <Sheet open={open} onOpenChange={setOpen} title="Ask" panelWidth={440}>
        <Conversation conversation={conversation} context={context} onClearContext={() => setContext(null)} autoFocus={open} />
      </Sheet>
    </AskContextValue>
  );
}
