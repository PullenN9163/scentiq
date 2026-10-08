# Fragrance advisor operations

## Configuration

Only FastAPI receives provider configuration. The browser and Next.js workload receive no provider key, endpoint, or deployment configuration. The BFF uses `API_INTERNAL_URL` and the signed-in member's Clerk token.

| Setting | Behavior |
| --- | --- |
| `AGENT_ENABLED` | Defaults to true. False bypasses inference and uses deterministic answers. |
| `AZURE_OPENAI_ENDPOINT` | HTTPS Azure OpenAI account origin or base ending `/openai/v1`. Blank uses fallback. |
| `AZURE_OPENAI_DEPLOYMENT` | Existing deployment name supporting Responses and function tools. Blank uses fallback. |
| `AZURE_CLIENT_ID` | Existing API managed identity client ID in Azure. |
| `AZURE_OPENAI_API_KEY` | Optional local-development credential. Ignored when a managed identity client ID is configured or in production. |
| `AGENT_PROMPT_VERSION` | Reviewed application policy version; currently `scentiq-agent-v1`. |
| `AGENT_MAX_TOOL_CALLS` | Default and maximum six total calls, including fallback. |
| `AGENT_MAX_TURNS` | Default and maximum four provider turns. |
| `AGENT_TIMEOUT_SECONDS` | Default and maximum 25 seconds, including fallback. |

Host development can use an Entra development credential through `DefaultAzureCredential` or the optional key. Keep actual values in a private environment file or secret manager. The Docker Compose example forwards provider settings only to `api`; a developer using a key should leave `AZURE_CLIENT_ID` blank. Leave endpoint and deployment blank to develop with deterministic responses.

## Azure prerequisite and IaC

An operator selects an existing Azure OpenAI or Foundry account and creates a model deployment in a region with Responses support and sufficient quota. Model provisioning is intentionally separate: regional model availability, deployment type, capacity, and quota must be chosen for the environment.

Set the subscription deployment parameters `foundryAccountName`, `foundryResourceGroupName`, optional `foundryProjectName`, `azureOpenAIEndpoint`, and `azureOpenAIDeployment`. The default development parameters remain empty until an account is selected. `agentEnabled` provides the deployment-level switch.

`infra/modules/agent-access.bicep` grants the API managed identity **Cognitive Services OpenAI User** at the selected account scope. It uses stable resource APIs (`Microsoft.CognitiveServices` 2025-06-01 and `Microsoft.Authorization` 2022-04-01), references the existing account/project, and does not create or modify them. The API Container App receives the endpoint and deployment, uses its existing managed identity, and receives no provider key or new Key Vault secret. An optional project is recorded by the integration; the application's inference path uses the account's v1 endpoint directly.

The deployment identity needs permission to create the role assignment at the selected account. If that account is in another resource group, an operator must grant the required scope or apply the module with a privileged deployment identity. Do not widen the application's identity roles. Allow time for RBAC propagation, then test a free-text Agent request and verify an authoritative card followed by streamed explanation.

## Checks and troubleshooting

Compile the subscription template and development parameters with the repository's normal Bicep workflow. Run both `infra/tests/Test-CompiledInfrastructure.ps1` and `infra/tests/Test-AgentInfrastructure.ps1` against the compiled subscription template; the latter verifies conditional RBAC, the inference-only role, existing-resource preservation, API-only configuration, and absence of a provider key. Store compiled review artifacts outside the public repository.

The subtle “AI explanation unavailable” state is expected when configuration is absent. With configuration present, inspect `agent_request` diagnostics for the error category, duration, deployment, and tool counts. An HTTP provider failure may indicate regional/model support, deployment name, capacity, endpoint, or RBAC propagation. Verify those settings without enabling raw provider or request logging. A `timeout` indicates the shared deadline was reached. A tool limit indicates the requested question needs a narrower scope. A missing context answer should be resolved in the member's Collection or Settings.

Stop cancels the browser request, propagates cancellation through the BFF, and closes the provider stream. A tool operation already running may finish its bounded calculation in its own session. No model-initiated collection/calendar writes are available.

Official references: [Azure OpenAI Responses API](https://learn.microsoft.com/en-us/azure/foundry/openai/how-to/responses), [v1 API lifecycle](https://learn.microsoft.com/en-us/azure/foundry/openai/api-version-lifecycle), and [stable account resource schema](https://learn.microsoft.com/en-us/azure/templates/microsoft.cognitiveservices/2025-06-01/accounts).
