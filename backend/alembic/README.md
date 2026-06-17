# Database migrations (Alembic)

We use [Alembic](https://alembic.sqlalchemy.org/) for schema migrations.
``app.database.init_db()`` still works on an empty DB (e.g. SQLite for
unit tests / first-run dev) but becomes a **no-op** once an
``alembic_version`` row exists — production deployments always use
migrations to keep schema in lockstep with code.

## Common commands

```bash
# Show current head
alembic current

# Show all heads
alembic heads

# Apply all pending migrations
alembic upgrade head

# Roll back the last migration
alembic downgrade -1

# Roll back everything (DESTRUCTIVE)
alembic downgrade base

# Generate a new migration from the current model state
alembic revision --autogenerate -m "add foo column"

# Generate an empty migration (for hand-written DDL or data migrations)
alembic revision -m "backfill something"
```

## In deployment

The Helm `backend` Deployment already runs `alembic upgrade head` as
an `initContainer` before the API pod starts.  In
``docker-compose.prod.yml`` the backend is configured to run the same
command on container start.

If you change a model, regenerate the migration in dev:

```bash
alembic revision --autogenerate -m "describe the change"
# Review the generated file under alembic/versions/
git add alembic/versions/*.py
git commit -m "schema: describe the change"
```

A CI guard (or a ``pre-commit`` hook) can run ``alembic upgrade head``
against a fresh DB + ``alembic check`` to catch drift.
