import { WeekPlanner } from "@/features/week/week-planner";
import { safeTimeZone } from "@/lib/calendar";
import {
  getCalendarRange,
  getCollection,
  getFragrance,
  getMe,
  getWeather,
} from "@/lib/server/queries";
import { buildWeek, nextDates, spanOf } from "@/lib/week";

export default async function WeekPage() {
  const [me, collection, weather] = await Promise.all([getMe(), getCollection(), getWeather()]);
  // The saved location's timezone decides where each day starts; UTC without one.
  const timeZone = safeTimeZone(me.preferences.timezone);
  const dates = nextDates(new Date(), timeZone);
  const { start, end } = spanOf(dates, timeZone);

  const owned = collection.filter((item) => item.status === "owned");
  const [details, calendar] = await Promise.all([
    Promise.all(owned.map((item) => getFragrance(item.fragrance.id))),
    getCalendarRange(start, end),
  ]);

  return (
    <WeekPlanner
      owned={details}
      days={buildWeek(dates, weather, calendar, timeZone)}
      timeZone={timeZone}
      temperatureUnit={weather.status === "ok" ? weather.forecast.temperature_unit : "fahrenheit"}
      weatherStatus={weather.status}
      calendarStatus={calendar.status}
      needsReconnect={calendar.status === "ok" && calendar.needsReconnect}
    />
  );
}
