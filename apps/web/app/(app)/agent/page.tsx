import { AgentExperience } from "@/features/agent/agent-experience";
import { safeTimeZone } from "@/lib/calendar";
import {
  getCalendarAround,
  getCollection,
  getFragrance,
  getInsights,
  getLayeringSuggestions,
  getMe,
  getWeather,
} from "@/lib/server/queries";
import { buildWeek, nextDates } from "@/lib/week";

export default async function AgentPage() {
  const [me, collection, insights, layering, weather, calendar] = await Promise.all([
    getMe(),
    getCollection(),
    getInsights(),
    getLayeringSuggestions("safe"),
    getWeather(),
    getCalendarAround(),
  ]);
  const owned = collection.filter((item) => item.status === "owned");
  const details = await Promise.all(owned.map((item) => getFragrance(item.fragrance.id)));

  const timeZone = safeTimeZone(me.preferences.timezone);
  const [day] = buildWeek(nextDates(new Date(), timeZone, 1), weather, calendar, timeZone);

  return (
    <AgentExperience
      owned={details}
      insights={insights}
      layering={layering}
      today={{
        day,
        timeZone,
        temperatureUnit: weather.status === "ok" ? weather.forecast.temperature_unit : "fahrenheit",
      }}
    />
  );
}
