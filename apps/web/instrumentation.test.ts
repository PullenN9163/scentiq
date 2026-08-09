import { afterEach, describe, expect, it, vi } from "vitest";

const useAzureMonitor = vi.fn();

vi.mock("@azure/monitor-opentelemetry", () => ({ useAzureMonitor }));

describe("server instrumentation", () => {
  afterEach(() => {
    vi.resetModules();
    vi.unstubAllEnvs();
    useAzureMonitor.mockReset();
  });

  it("does nothing outside the Node.js runtime", async () => {
    vi.stubEnv("NEXT_RUNTIME", "edge");
    vi.stubEnv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=test");

    const { register } = await import("./instrumentation");
    await register();

    expect(useAzureMonitor).not.toHaveBeenCalled();
  });

  it("configures Azure Monitor for the Node.js runtime", async () => {
    vi.stubEnv("NEXT_RUNTIME", "nodejs");
    vi.stubEnv("APPLICATIONINSIGHTS_CONNECTION_STRING", "InstrumentationKey=test");

    const { register } = await import("./instrumentation");
    await register();

    expect(useAzureMonitor).toHaveBeenCalledOnce();
    expect(useAzureMonitor).toHaveBeenCalledWith({
      azureMonitorExporterOptions: {
        connectionString: "InstrumentationKey=test",
        disableOfflineStorage: true,
      },
      enableTraceBasedSamplingForLogs: true,
    });
  });
});
