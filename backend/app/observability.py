"""Observability initialisation (Sentry + OpenTelemetry).

We treat SENTRY_DSN and OTEL_EXPORTER_OTLP_ENDPOINT as **opt-in**:
when the env var is empty the corresponding SDK is not installed at
runtime, so this is a no-op in development.  Both integrations are
safe to import without the SDKs being present — the modules below
only ``import sentry_sdk`` / ``opentelemetry.*`` after the env-var
check, and they degrade gracefully on import failure.
"""
from __future__ import annotations

import logging
import os
from typing import Optional

from app.config import settings


logger = logging.getLogger(__name__)


_sentry_initialised = False
_tracing_initialised = False


def init_sentry() -> bool:
    """Initialise Sentry if ``SENTRY_DSN`` is set.

    Returns ``True`` if Sentry was started, ``False`` otherwise.
    """
    global _sentry_initialised
    if _sentry_initialised:
        return True
    dsn = os.getenv("SENTRY_DSN", "").strip()
    if not dsn:
        logger.info("Sentry disabled (SENTRY_DSN not set)")
        return False
    try:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.logging import LoggingIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration

        sentry_sdk.init(
            dsn=dsn,
            environment=os.getenv("SENTRY_ENV", "development"),
            release=os.getenv("SENTRY_RELEASE", settings.APP_NAME),
            traces_sample_rate=float(os.getenv("SENTRY_TRACES_SAMPLE_RATE", "0.1")),
            profiles_sample_rate=float(os.getenv("SENTRY_PROFILES_SAMPLE_RATE", "0.0")),
            integrations=[
                FastApiIntegration(transaction_style="endpoint"),
                SqlalchemyIntegration(),
                LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
            ],
            send_default_pii=False,
        )
        _sentry_initialised = True
        logger.info("Sentry initialised (env=%s)", os.getenv("SENTRY_ENV", "development"))
        return True
    except ImportError:
        logger.warning("sentry-sdk not installed; skipping")
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("Sentry init failed: %s", exc)
        return False


def init_tracing() -> bool:
    """Initialise OpenTelemetry if ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set.

    Sets up a ``TracerProvider`` that exports OTLP spans to the given
    endpoint, then auto-instruments FastAPI / SQLAlchemy / httpx so
    we get a free distributed-tracing story without changing call
    sites.
    """
    global _tracing_initialised
    if _tracing_initialised:
        return True
    endpoint = os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip()
    if not endpoint:
        logger.info("OpenTelemetry disabled (OTEL_EXPORTER_OTLP_ENDPOINT not set)")
        return False
    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        resource = Resource.create(
            {
                "service.name": os.getenv("OTEL_SERVICE_NAME", settings.APP_NAME.lower().replace(" ", "-")),
                "service.version": os.getenv("SENTRY_RELEASE", "0.1.0"),
                "deployment.environment": os.getenv("SENTRY_ENV", "development"),
            }
        )
        provider = TracerProvider(resource=resource)
        provider.add_span_processor(
            BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, insecure=True))
        )
        trace.set_tracer_provider(provider)
        # Auto-instrument: must be done at startup, after FastAPI app
        # exists and after SQLAlchemy engine is built.  Stash the
        # instrumentor functions so main.py can call them at the
        # right moment.
        _tracing_initialised = True
        logger.info("OpenTelemetry initialised, endpoint=%s", endpoint)
        return True
    except ImportError as exc:
        logger.warning("OpenTelemetry packages not installed: %s", exc)
        return False
    except Exception as exc:  # noqa: BLE001
        logger.warning("OTel init failed: %s", exc)
        return False


def instrument_app(app) -> None:
    """Hook OTel instrumentors into the FastAPI app + SQLAlchemy engine.

    Safe to call even when tracing is disabled (it's a no-op).
    """
    if not _tracing_initialised:
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        try:
            from app.database import engine

            SQLAlchemyInstrumentor().instrument(engine=engine)
        except Exception:
            pass
        try:
            HTTPXClientInstrumentor().instrument()
        except Exception:
            pass
    except Exception as exc:  # noqa: BLE001
        logger.warning("OTel instrumentation failed: %s", exc)


def capture_exception(exc: Exception) -> None:
    """Best-effort error capture.  Safe to call without Sentry."""
    if not _sentry_initialised:
        return
    try:
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
    except Exception:
        pass


def get_tracer(name: Optional[str] = None):
    """Return a tracer; works whether or not OTel is initialised."""
    try:
        from opentelemetry import trace

        return trace.get_tracer(name or settings.APP_NAME)
    except Exception:
        # Return a no-op tracer
        class _NoopSpan:
            def __enter__(self): return self
            def __exit__(self, *args): return False
            def set_attribute(self, *args, **kwargs): pass
            def set_status(self, *args, **kwargs): pass
            def end(self): pass
            def record_exception(self, *args, **kwargs): pass
        class _NoopTracer:
            def start_as_current_span(self, *_args, **_kwargs): return _NoopSpan()
        return _NoopTracer()
