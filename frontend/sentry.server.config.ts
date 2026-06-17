// Sentry server-side config.  Loaded by @sentry/nextjs's build plugin
// when ``@sentry/nextjs`` is in the dependencies.  It is intentionally
// empty so that the SDK doesn't crash when the package isn't
// installed (we install it lazily via dynamic import in
// ``lib/observability.ts``).

export {};
