import { CloudSun } from "lucide-react";
import Link from "next/link";

import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  conditionLabel,
  formatPrecipitation,
  formatTemperature,
  type WeatherResult,
} from "@/lib/weather";

/** Today's forecast for the member's saved location, or why it is missing. */
export function WeatherCard({ weather }: { weather: WeatherResult }) {
  return (
    <Card>
      <CardContent>
        <div className="section-title">
          <CloudSun size={19} />
          <h3>Weather</h3>
        </div>
        <WeatherBody weather={weather} />
      </CardContent>
    </Card>
  );
}

function WeatherBody({ weather }: { weather: WeatherResult }) {
  if (weather.status === "location_required" || weather.status === "location_unresolved") {
    return (
      <>
        <p className="muted">
          {weather.status === "location_required"
            ? "Add your location in Settings to see today's forecast."
            : "We couldn't find your saved location. Check it in Settings."}
        </p>
        <Button asChild variant="ghost">
          <Link href="/settings">Open settings</Link>
        </Button>
      </>
    );
  }

  if (weather.status === "unavailable") {
    return (
      <p className="muted" role="status">
        The forecast is unavailable right now. Try again shortly.
      </p>
    );
  }

  const { forecast } = weather;
  const today = forecast.days[0];
  if (!today) {
    return <p className="muted">No forecast is available for today yet.</p>;
  }
  const unit = forecast.temperature_unit;
  const rain = formatPrecipitation(today.precipitation_probability);

  return (
    <>
      <p>
        <strong className="metric-number">{formatTemperature(today.high_celsius, unit)}</strong>
        {today.low_celsius === null ? null : (
          <span className="muted"> / {formatTemperature(today.low_celsius, unit)}</span>
        )}
      </p>
      <p>
        {conditionLabel(today.condition)}
        {rain ? ` · ${rain}` : ""}
      </p>
      <p className="muted">{forecast.location_label}</p>
      {forecast.stale ? (
        <p className="muted" role="status">
          Showing the last forecast we fetched; the weather service is unreachable.
        </p>
      ) : null}
    </>
  );
}
