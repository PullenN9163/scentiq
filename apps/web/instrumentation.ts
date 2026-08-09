export async function register() {
  const connectionString = process.env.APPLICATIONINSIGHTS_CONNECTION_STRING;

  if (process.env.NEXT_RUNTIME !== "nodejs" || !connectionString) {
    return;
  }

  const { useAzureMonitor: configureAzureMonitor } = await import(
    "@azure/monitor-opentelemetry"
  );
  configureAzureMonitor({
    azureMonitorExporterOptions: {
      connectionString,
      disableOfflineStorage: true,
    },
    enableTraceBasedSamplingForLogs: true,
  });
}
