# Alpha — Secret Rotation Checklist

**Status: REQUIRED operator action before any production deploy.**

Per audit ALP-C01 / ALP-H02, the on-disk `.env` and `packages/api/.env`
contain real-looking secret values. Per the project's "Larangan keras"
in AGENTS.md, these files are gitignored and have been verified never
to enter history. They are, however, plaintext at rest on every
developer's machine and on any container image that includes them.

## Values to rotate NOW

1. **`GEMINI_API_KEY`** (root `.env`, `packages/api/.env`)
   - Multiple comma-separated keys in `packages/api/.env`
   - Action: revoke at Google AI Studio; mint replacement keys; store
     in a real secret manager (1Password / HashiCorp Vault / Doppler);
     load at boot via `EnvironmentFile` in compose or a secret
     reference in k8s.

2. **`FINANCE_TRACKER_API_KEY`** (root `.env`)
   - Action: rotate the master key; update all clients. The on-disk
     value grants admin scope.

3. **`SECRET_KEY`** (root `.env`)
   - Currently unused by code (audit ALP-H01). Document this status
     in code, OR wire a real JWT layer. Until then, treat as
     reserved and do not put a real value here.

4. **`TELEGRAM_BOT_TOKEN`** (`packages/api/.env`)
   - Action: revoke via @BotFather; mint new token; redeploy.

5. **`DATABASE_URL`** — the password portion (root `.env:2`)
   - Currently `CHANGE_ME` literal; this is the placeholder from
     `docker-compose.yml`'s default `postgres:postgres`. Set a real
     password; update `docker-compose.yml` or its env-file substitute.

## Pre-commit guardrails (already added)

- `.pre-commit-config.yaml` runs `detect-secrets` against a baseline
  and `gitleaks` on every commit. Any NEW secret in a tracked file
  fails the commit. Existing secrets in `.env*` are ignored because
  those files are gitignored — `.pre-commit-config.yaml` does NOT
  re-introduce them to the tree.

- Operators should run `detect-secrets scan --baseline .secrets.baseline`
  in CI to confirm the working tree has no new secret markers in
  tracked files.

## Storage target

Move to a real secret manager. Until then, keep `.env*` out of
history and out of container images:

```dockerfile
# Dockerfile idiom
COPY .env.example .env.example
# DO NOT COPY .env — let the runtime inject via env_file or k8s secret.
```

Compose:

```yaml
services:
  api:
    env_file:
      - .env.production  # operator-managed, gitignored
```

## Verification

After rotation, restart the API and confirm:

```bash
curl -fsS http://127.0.0.1:8444/api/health
# Expect 200 with no "missing API key" warnings in the log.
```

Then run:

```bash
git grep -E "(AIza|sk-|ghp_|xox[abp]-|TELEGRAM_BOT_TOKEN=)" -- ':!.env*' ':!docs/'
# Expect no output.
```

(That is a coarse check; the pre-commit hooks are the authoritative gate.)
