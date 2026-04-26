# AutoFaCodex

## Local Setup

1. Copy the example environment file:
   ```bash
   cp .env.example .env
   ```
2. Set `HOST_CODEX_HOME` in `.env` to your host Codex config directory. On this machine, use:
   ```bash
   HOST_CODEX_HOME=/home/alvin/.codex
   ```
3. Do not commit `.env`, `auth.json`, or `config.toml`.
4. Start the stack:
   ```bash
   docker compose up --build
   ```

## Worker Codex Auth Mounts

The worker container reads host Codex auth config through read-only mounts:

```text
${HOST_CODEX_HOME}/auth.json -> /home/worker/.codex/auth.json:ro
${HOST_CODEX_HOME}/config.toml -> /home/worker/.codex/config.toml:ro
```

## Test Samples

PDF test samples live in `pdf-to-ppt-test-samples/`.

## Smoke Test

The smoke test starts Docker services and runs Prisma migrations from the host. Install host Node/npm dependencies first:

```bash
npm install
```

By default, the script derives a host database URL from `DATABASE_URL` by replacing the compose hostname `postgres` with `localhost`. If your host needs a different database URL, set `HOST_DATABASE_URL` in `.env`.

The script sources `.env` as shell, so quote or escape values that contain shell-special characters.

The script expects committed Prisma migrations under `apps/web/prisma/migrations/`; this repo includes the initial migration. If migrations are missing, it fails before starting Docker because `prisma:migrate` would otherwise prompt for a migration name.

Run the Docker smoke test from the repository root:

```bash
scripts/smoke-test.sh
```
