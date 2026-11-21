"use client";

import { Conversation } from "./ask-thread";
import { useAskConversation } from "./ask-provider";
import { useConversation } from "./use-ask-thread";
import styles from "./ask.module.css";

/** The full-page fallback for Ask at /agent, sharing the panel's conversation. */
export function AskPage() {
  const shared = useAskConversation();
  const local = useConversation(true);
  return (
    <div className="at-page">
      <h1 className={`at-display-lg ${styles.pageTitle}`}>Ask</h1>
      <Conversation conversation={shared ?? local} layout="page" autoFocus />
    </div>
  );
}
