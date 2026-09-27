"use client";

import { ArrowRight, Sparkles } from "lucide-react";
import Link from "next/link";
import { useState } from "react";

import { PageHeader } from "@/components/shared/page-header";
import { Badge } from "@/components/ui/badge";
import { occasionLabel } from "@/lib/calendar";
import { rankFragrances, seasonForMonth } from "@/lib/catalog-ranking";
import { conditionLabel, formatTemperature } from "@/lib/weather";
import { contextFor, type PlanDay } from "@/lib/week";
import type {
  CollectionInsights,
  FragranceDetail,
  LayeringSuggestion,
  TemperatureUnit,
} from "@/types/api";

const prompts = ["What should I wear today?", "What is my most worn fragrance?", "What can I layer?"] as const;

/** What "today" holds for the member, when a forecast or calendar supplies it. */
export interface AgentToday {
  day: PlanDay;
  timeZone: string;
  temperatureUnit: TemperatureUnit;
}

function todayReasons(today: AgentToday): string {
  const reasons: string[] = [];
  const { weather, events } = today.day;
  if (weather) {
    reasons.push(
      `${formatTemperature(weather.high_celsius, today.temperatureUnit)} and ${conditionLabel(weather.condition).toLowerCase()}`,
    );
  }
  const occasion = contextFor(today.day, today.timeZone).occasion;
  const lead = occasion ? events.find((event) => event.occasion === occasion) : undefined;
  if (lead) reasons.push(`your ${occasionLabel(lead.occasion).toLowerCase()} plans (${lead.title})`);
  return reasons.length ? ` with ${reasons.join(" and ")}` : "";
}

export function AgentExperience({
  owned,
  insights,
  layering,
  today = null,
}: {
  owned: FragranceDetail[];
  insights: CollectionInsights;
  layering: LayeringSuggestion[];
  today?: AgentToday | null;
}) {
  const [answer, setAnswer] = useState<string | null>(null);
  function ask(prompt: (typeof prompts)[number]) {
    if (owned.length === 0) {
      setAnswer("Your owned collection is empty. Add a fragrance before asking for a collection-based answer.");
      return;
    }
    if (prompt === prompts[0]) {
      const now = new Date();
      const context = today
        ? contextFor(today.day, today.timeZone)
        : {
            season: seasonForMonth(now.getMonth()),
            daypart: now.getHours() >= 17 ? ("night" as const) : ("day" as const),
            coolWeather: now.getMonth() < 2 || now.getMonth() > 9,
          };
      const best = rankFragrances(owned, context)[0];
      setAnswer(
        `${best.name} is the strongest catalog-supported match in your collection for today${today ? todayReasons(today) : ""}.`,
      );
      return;
    }
    if (prompt === prompts[1]) {
      const most = insights.most_worn[0];
      setAnswer(most ? `${most.fragrance_name} leads your wear history with ${most.wear_count} wears.` : "You have not logged a wear yet.");
      return;
    }
    const pair = layering[0];
    setAnswer(pair ? `${pair.first.name} + ${pair.second.name} is your highest-ranked ${pair.mode} pairing.` : "Add at least two owned fragrances to receive layering guidance.");
  }
  const uses = today && (today.day.weather || today.day.events.length > 0);
  return (
    <section className="page agent-page">
      <PageHeader
        eyebrow="Collection advisor"
        title="Ask ScentIQ"
        description="Deterministic answers grounded in your persisted collection and insights."
      />
      <p className="muted" role="note">
        {uses
          ? "Answers about today use your forecast and connected calendars."
          : "Add a location and connect a calendar in Settings, and answers about today will use them."}
      </p>
      <div className="agent-shell">
        <div className="conversation" aria-live="polite">
          {answer ? (
            <div className="agent-bubble">
              <Badge>Collection answer</Badge>
              <p>{answer}</p>
              <Link href="/collection">
                Open collection <ArrowRight size={15} />
              </Link>
            </div>
          ) : (
            <div className="agent-welcome">
              <Sparkles />
              <h2 className="serif">What would you like to decide?</h2>
            </div>
          )}
        </div>
        <div className="quick-prompts">
          {prompts.map((prompt) => (
            <button key={prompt} onClick={() => ask(prompt)}>
              {prompt}
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
