import { AgentExperience } from "@/features/agent/agent-experience";
import { AskPage } from "@/features/ask/ask-page";
import { isAtelierEnabled } from "@/lib/atelier-flag";

export default function AgentPage() {
  return isAtelierEnabled() ? <AskPage /> : <AgentExperience authenticated />;
}
