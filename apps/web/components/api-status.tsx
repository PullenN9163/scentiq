"use client";

import { useEffect, useState } from "react";

import type { ApiAvailability } from "@/lib/api-status";

type ApiStatusState = "checking" | ApiAvailability;

const labels: Record<ApiStatusState, string> = {
  checking: "Checking API",
  available: "API available",
  unavailable: "API unavailable",
};

export function ApiStatus() {
  const [status, setStatus] = useState<ApiStatusState>("checking");

  useEffect(() => {
    let active = true;

    async function checkApi() {
      try {
        const response = await fetch("/api/status", { cache: "no-store" });
        const payload: unknown = await response.json();
        const availability =
          response.ok &&
          typeof payload === "object" &&
          payload !== null &&
          "api" in payload &&
          payload.api === "available"
            ? "available"
            : "unavailable";

        if (active) {
          setStatus(availability);
        }
      } catch {
        if (active) {
          setStatus("unavailable");
        }
      }
    }

    void checkApi();

    return () => {
      active = false;
    };
  }, []);

  return (
    <div
      className={`api-status api-status--${status}`}
      role="status"
      aria-atomic="true"
      aria-live="polite"
    >
      <span className="api-status__dot" aria-hidden="true" />
      <span>{labels[status]}</span>
    </div>
  );
}
