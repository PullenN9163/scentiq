import { WeekPlanner } from "@/features/week/week-planner";
import { safeTimeZone, type CalendarResult } from "@/lib/calendar";
import { getCalendarRange, getWeather, getWeekPage } from "@/lib/server/queries";
import type { WeatherResult } from "@/lib/weather";
import { buildWeek, nextDates, spanOf } from "@/lib/week";

export default async function WeekPage() {
  const weatherPromise: Promise<WeatherResult> = getWeather();
  const page = await getWeekPage();
  const timeZone = safeTimeZone(page.me.preferences.timezone);
  const dates = nextDates(new Date(), timeZone);
  const { start, end } = spanOf(dates, timeZone);
  const [weather, calendar]: [WeatherResult, CalendarResult] = await Promise.all([
    weatherPromise,
    getCalendarRange(start, end),
  ]);

  return (
    <WeekPlanner
      owned={page.owned}
      days={buildWeek(dates, weather, calendar, timeZone)}
      timeZone={timeZone}
      temperatureUnit={weather.status === "ok" ? weather.forecast.temperature_unit : "fahrenheit"}
      weatherStatus={weather.status}
      calendarStatus={calendar.status}
      needsReconnect={calendar.status === "ok" && calendar.needsReconnect}
    />
  );
}
