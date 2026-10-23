# Public demonstration

Target: **https://saipport.gulevskii.dev**. Deploy this project independently of existing sites and databases. The application remains a synthetic demonstration with isolated visitor workspaces; it is not a shared production support system.

## Runtime

Use Docker Compose 2.24+ (the demonstration host uses Compose 5). Keep the checkout and a private `.env` on the host. Generate secrets with `python3 scripts/configure.py`; preserve `.env` during upgrades and set mode `0600`.

Public settings:

```dotenv
APP_PORT=18080
SECURE_COOKIES=true
ALLOWED_ORIGINS=https://saipport.gulevskii.dev
MODEL_PROVIDER=deterministic
TOOL_TRANSPORT=mcp
SESSION_LIMIT_PER_HOUR=30
GLOBAL_SESSIONS_PER_HOUR=100
GLOBAL_ACTIVE_RUNS=6
LIVE_CALLS_PER_DAY=40
```

An optional OpenRouter key is provided separately, never in source or build arguments. Only free models are permitted. The default offline driver keeps the demonstration reproducible when the development key expires or a free provider is unavailable.

The API binds to host loopback on port 18080 for local diagnostics. PostgreSQL and the laboratory have no published ports. The API, worker, and laboratory use a non-root user, read-only root filesystem, bounded temporary storage, dropped capabilities, and process/memory limits. Container logs rotate.

## Networks and proxy

The application has its own private Compose network and database volume. A second, dedicated `saipport-edge` bridge connects only the API and the existing reverse proxy:

```sh
docker network create --subnet 172.30.40.0/24 saipport-edge
docker network connect --ip 172.30.40.2 saipport-edge mayak-proxy
docker compose -f compose.yaml -f deploy/compose.demo.yaml up -d --build --wait
```

Check for an existing network/attachment before repeating these commands. The API has the fixed edge address `172.30.40.3`. Uvicorn trusts forwarding headers only from the proxy's exact edge address. The proxy overwrites forwarded client headers. The proxy is not attached to the private application/database network.

`nginx.conf` is a new server configuration for this hostname only. `upstream.conf` is its private upstream include. Install both under the proxy's persisted `/data/saipport/` directory, then include `/data/saipport/site.conf` once from the existing proxy's HTTP-level custom include. Preserve the previous include file before editing it. Validate with `nginx -t` before a graceful reload.

Bootstrap the HTTP challenge server before installing the TLS block. Create an **A** record named `saipport` for the demonstration host. Obtain the certificate with the proxy's existing Certbot account and webroot `/data/letsencrypt-acme-challenge`; install the complete TLS configuration only after certificate issuance succeeds. Never disable TLS validation to make the demo work.

The public proxy applies per-client connection and request limits, tighter limits for session provisioning and run creation, a 64KB request body cap, and SSE-compatible unbuffered proxying. The application adds global and per-workspace quotas. An IP can hit a temporary request limit while creating many fresh role workspaces; wait and retry.

Reattaching the proxy to `saipport-edge` is required if another administrator recreates that proxy container without preserving its added network. Ordinary restarts retain the attachment.

## Upgrade and rollback

1. Record the current Git SHA and run `./deploy/backup.sh` before changing data-bearing releases.
2. Fetch a reviewed commit from the public repository. Preserve `.env` and the PostgreSQL volume.
3. Run the Compose command above. The migration service applies checksum-verified, forward-only migrations before application services start.
4. Verify `/ready`, a fresh isolated workspace, investigation/approval/verification, static assets, and existing hostnames.
5. For an application-only rollback, check out the previous SHA and rebuild/recreate API, worker, and laboratory. Do not remove the database volume. Database rollback requires restoring a matched backup pair; do not pretend arbitrary schema downgrades are supported.

## Backup and retention

From the checkout, run:

```sh
./deploy/backup.sh /var/backups/saipport
```

This briefly stops the application services, saves a consistent `pg_dump -Fc` pair for product and laboratory, validates the archive listings, and restarts the services through a trap. It does not touch other Compose projects. Backup files have private permissions and stay outside Git. Restore into empty databases with the matching owners using `pg_restore --no-owner`, then run migrations and restart the application.

Expired demo workspaces are removed in bounded batches by the worker every ten minutes. Active queued/running jobs are retained until they finish; sessions expire after 24 hours. No visitor data should be treated as durable customer records. Failed laboratory cleanup preserves the product workspace for a later retry.

The host also needs certificate renewal and log rotation for this new hostname. Renewal must target this certificate only, validate its result, and gracefully reload the proxy. Backups and renewal should be observed separately from the API readiness endpoint.

## Deployment verification

Rollout checks and the deployed revision are recorded here after the first successful deployment. API `/ready` checks product PostgreSQL and the laboratory; the browser execution check also verifies the worker and its MCP path. A healthy `/ready` alone does not prove the worker is running.
