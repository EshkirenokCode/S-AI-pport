# Local operation and deployment preparation

## Prerequisites and configuration

Docker Compose is the portable path. Native development needs Python 3.12+, Node 24+, and PostgreSQL 17 binaries. `scripts/configure.py` generates `.env` only when it does not exist and preserves an existing file. Never commit that file. Lock files pin application dependencies; container base images track the documented major releases.

| Variable | Purpose |
| --- | --- |
| APP_SECRET | HMAC signing for run-bound local MCP delegation |
| SANDBOX_TOKEN | Service-to-service authentication, never sent to the model |
| DATABASE_URL | Product PostgreSQL; worker/API only |
| SANDBOX_DATABASE_URL | Laboratory PostgreSQL; lab/migration process only in Compose |
| POSTGRES_PASSWORD / APP_DB_PASSWORD / LAB_DB_PASSWORD | Separate Compose database credentials |
| MODEL_PROVIDER | deterministic or openrouter; recorded on every run |
| OPENROUTER_API_KEY / OPENROUTER_MODEL | Optional live credential and free model/router |
| TOOL_TRANSPORT | mcp (default) or direct (same registry, useful for debugging) |
| APP_URL / SANDBOX_URL | Fixed trusted service locations; never model arguments |
| SECURE_COOKIES / ALLOWED_ORIGINS | HTTPS cookie policy and exact browser origins |
| LIVE_CALLS_PER_DAY | Global database-enforced live request quota, default 40 |
| RUNS_PER_TENANT / SESSION_LIMIT_PER_HOUR | Workspace/run and session provisioning quotas |
| RUN_TIMEOUT_SECONDS / MAX_MODEL_CALLS / MAX_MODEL_TOKENS / MAX_TOOL_CALLS | Per-run limits |
| LEASE_SECONDS | Renewable worker lease, default 30 seconds |

Default limits are a 240-second run, eight model calls, 24,000 observed model tokens, 18 tool calls, three worker acquisitions, three concurrent queued/running jobs per workspace, 40 total runs per workspace, and expiring 24-hour sessions. Model token accounting is checked before the next call; a single response may cross the cumulative threshold before the run is stopped. Calls also have their own bounded response size and HTTP timeout.

## Start and stop

`docker compose up --build --wait` builds the frontend, creates separate database users/databases, applies checksum-verified migrations, and starts the API, laboratory, and worker. Only `127.0.0.1:8000` is published. `docker compose down` preserves the database volume; removing that volume destroys demo data.

`make dev` uses an isolated `.local/pg` cluster on port 55432 and launches the development services. It never reuses the system PostgreSQL data directory. Ctrl+C stops application processes. To stop the retained cluster, use the matching PostgreSQL binary: `pg_ctl -D .local/pg stop`.

`/health` is API liveness. `/ready` checks product PostgreSQL and the authenticated laboratory. A stopped worker does not make `/ready` fail; queue state and worker acquisitions must also be inspected. The UI Run details and Workspace activity expose per-run usage, failures, retries/acquisitions, and decisions.

## Recovery

Graceful shutdown releases the current lease for recovery. After a crash, another worker claims an expired lease with `SKIP LOCKED` and continues from the persisted checkpoint. An approval survives restarts and receives a new bounded execution deadline. A mutation uses the proposal UUID as its idempotency key.

After an ambiguous operation result, the executor reads the laboratory's operation receipt before considering another mutation. Recovered receipts lead to a fresh verification. A missing/uncertain receipt is escalated. Stale account versions require a new investigation. Never manually change a proposal payload; a database trigger rejects it.

## Backup and restore

For an offline local backup, stop API/worker/laboratory, retain PostgreSQL, and use `pg_dump -Fc` separately for the product and laboratory databases. Keep both snapshots together; they contain linked operation IDs and account references. Store backups outside the repository with access limited to the operator.

For Compose, run `pg_dump` inside the postgres container as its administrative user, once for `saipport` and once for `saipport_lab`, redirecting outputs to private local files. For restore, provision empty databases with the matching owners, use `pg_restore --no-owner` under the respective database owner, and run migrations before restarting services. Test restores in an isolated environment. No automatic backup scheduler is included.

## Publishing later

Use a separate deployment environment. Configure an explicit HTTPS origin, `SECURE_COOKIES=true`, and proxy trust restricted to the actual reverse proxy. PostgreSQL and the lab remain private; never publish their ports. Keep global and per-workspace quotas, resource limits, and sandbox-only roles in place. Add a separate ingress/session policy if exposing an anonymous demo at scale.

The existing portfolio and other projects are not deployment targets for these commands. No public deployment or production identity provider is included in this delivery.
