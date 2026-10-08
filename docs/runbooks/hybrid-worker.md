# Hybrid recommendation worker

The hybrid worker moves CPU-heavy recommendation scoring off the live request path. Azure remains the source of truth and serves all web traffic. The home worker only makes outbound HTTPS calls to Azure Storage, receives versioned job documents, and publishes versioned result documents. It has no PostgreSQL, Clerk, Key Vault, or member-email access.

## Runtime shape

- Azure Container Apps runs a scheduled `hybrid-bridge` job every minute. It dispatches pending database jobs to `hybrid-jobs` and promotes messages from `hybrid-results`.
- Azure Storage keeps job bodies in the private `system` container and pointers in `hybrid-jobs`, `hybrid-results`, and `hybrid-jobs-poison`. A lifecycle rule removes job bodies after two days.
- The home server runs the worker continuously. Five failed deliveries move a job to the poison queue. Replayed results are idempotent, and results for an obsolete input version are rejected.
- A missing or offline worker does not break pages. The API returns the newest snapshot, or computes the existing synchronous fallback on a cache miss.

## Home server baseline

Create an Ubuntu 24.04 LTS Generation 2 Hyper-V VM with 2 virtual CPUs, 4 GB memory, and a 40 GB dynamically expanding disk. Use an external virtual switch or NAT with outbound TCP 443. Do not expose inbound application ports through the home router.

Patch the VM, enable automatic security updates, and create a non-login `scentiq-worker` service account. Keep `/opt/scentiq` owned by root and `/var/lib/scentiq-worker` owned by the service account.

## Azure identity and RBAC

1. Onboard the Ubuntu VM as an Azure Arc-enabled server and confirm its system-assigned managed identity is active.
2. Set `hybridWorkerPrincipalId` to the Arc machine identity's object ID in the environment deployment parameters. Deploying the Bicep grants Storage Blob Data Contributor only on the private `system` container and Storage Queue Data Contributor only on the three hybrid queues.
3. Add the service account to the local group authorized to read the Azure Arc managed-identity challenge token, then restart its session. Do not loosen permissions on `/var/opt/azcmagent/tokens`.
4. Verify token acquisition from the VM before enabling the service. Azure Arc exposes its local identity endpoint on port 40342; the service environment explicitly selects `ManagedIdentityCredential`.

The worker must not receive a database URL, Clerk secret, storage key, SAS token, or Azure client secret.

## Install and start

Deploy the same reviewed `dev` revision used to build the Azure API image:

```bash
sudo install -d -o root -g root -m 0755 /opt/scentiq
sudo install -d -o scentiq-worker -g scentiq-worker -m 0750 /var/lib/scentiq-worker
sudo git clone --branch dev --depth 1 https://github.com/PullenN9163/scentiq.git /opt/scentiq
cd /opt/scentiq/apps/api
sudo uv sync --frozen --no-dev
sudo install -d -m 0750 /etc/scentiq
sudo install -o root -g scentiq-worker -m 0640 ../../ops/systemd/hybrid-worker.env.example /etc/scentiq/hybrid-worker.env
sudo install -o root -g root -m 0644 ../../ops/systemd/scentiq-hybrid-worker.service /etc/systemd/system/
```

Replace the storage account placeholder in `/etc/scentiq/hybrid-worker.env`, then enable the unit:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now scentiq-hybrid-worker
sudo systemctl status scentiq-hybrid-worker
```

## Verification and operations

Change a collection item in ScentIQ, then confirm this sequence within five minutes:

1. The Azure bridge job succeeds and `hybrid-jobs` briefly gains a message.
2. The worker journal records no authentication or validation error.
3. `hybrid-results` is consumed by a later bridge run.
4. `GET /api/v1/recommendations` reports `refresh_status: fresh` for the new `input_version`.

Useful checks:

```bash
journalctl -u scentiq-hybrid-worker --since "15 minutes ago"
systemctl show scentiq-hybrid-worker -p ActiveState -p NRestarts
```

Alert when the oldest queue message is over five minutes, poison messages are nonzero, the bridge job fails, or the worker is inactive. To pause home processing safely, stop the service; Azure pages continue using snapshots and fallback scoring. Do not purge queues during an outage.

For rollback, disable the service and scheduled bridge job. Existing synchronous endpoints remain available throughout rollout.
