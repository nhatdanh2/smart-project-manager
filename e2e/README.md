# End-to-end tests (Playwright)

We use [Playwright](https://playwright.dev/) for full-stack end-to-end
tests.  The tests drive the real API + UI the way a user would, so
they're the most realistic safety net we have.

## What we cover

| Spec | What it tests |
| --- | --- |
| `auth.spec.ts` | register/login round trip, 401 on bad password, 401 on missing token, 429 after 10 failed logins |
| `kanban.spec.ts` | create project + recurring task, move to done, verify spawned occurrence; CPM recalc |
| `file-preview.spec.ts` | upload PNG, meta + preview + range requests, 403 for non-member |
| `presence.spec.ts` | two users WS-connect, presence broadcast includes both |

## Local development

```bash
# 1. Install Playwright + browser binaries
cd e2e
npm install
npx playwright install --with-deps chromium

# 2. Start the local stack (Postgres + Redis + API + Frontend)
cd ..
docker compose up -d

# 3. Run the suite
cd e2e
npm test

# 4. Run a single file in headed mode
npm run test:headed -- auth.spec.ts

# 5. Generate the HTML report
npm run report
```

## CI

The `ci` workflow in `.github/workflows/ci.yml` runs the suite against
a fresh service-container Postgres + Redis.  The `e2e` job depends on
`backend` and `frontend` jobs passing first.

## Pointing at staging

```bash
PLAYWRIGHT_BASE_URL=https://staging.spm.example.com \
PLAYWRIGHT_API_URL=https://staging.spm.example.com \
  npm test
```

When ``PLAYWRIGHT_BASE_URL`` is set, Playwright skips the
``webServer`` step and assumes the stack is already up.

## Adding a new test

1. Create ``tests/<feature>.spec.ts``.
2. Use the helpers in ``tests/helpers/`` (``randomUser``, ``register``,
   ``login``) to authenticate.
3. Prefer API calls for setup and ``page.locator(...)`` for the UI
   assertion — fast and reliable.
4. Always tear down the API context (``await api.dispose()``) so the
   suite doesn't leak sockets between tests.
