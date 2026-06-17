# Smart PM Helm Chart

Production-ready Helm chart for the Smart Student Project Manager.

## Install

```bash
# 1. Lint the chart
helm lint helm/smart-pm

# 2. Render the manifests to see what will be applied
helm template smart-pm helm/smart-pm \
  --set backend.secrets.jwtSecretKey=dev-jwt \
  --set backend.secrets.postgresPassword=dev-pw

# 3. Install (with bundled Postgres + Redis for dev)
helm upgrade --install smart-pm helm/smart-pm \
  --namespace smart-pm --create-namespace \
  --set backend.secrets.jwtSecretKey=$(openssl rand -hex 32) \
  --set backend.secrets.postgresPassword=$(openssl rand -hex 16) \
  --set backend.image.tag=0.1.0 \
  --set frontend.image.tag=0.1.0

# 4. With a custom values file
helm upgrade --install smart-pm helm/smart-pm \
  -f helm/smart-pm/values.prod.yaml \
  --namespace smart-pm
```

## Configuration

The most important values (full list in `values.yaml`):

| Key | Type | Default | Description |
| --- | --- | --- | --- |
| `backend.image.tag` | string | `latest` | Backend image tag |
| `frontend.image.tag` | string | `latest` | Frontend image tag |
| `backend.replicaCount` | int | `2` | API replicas |
| `backend.autoscaling.enabled` | bool | `true` | HPA for backend |
| `backend.secrets.jwtSecretKey` | string | *required* | JWT secret |
| `backend.secrets.postgresPassword` | string | *required* | DB password |
| `backend.secrets.anthropicApiKey` | string | `""` | Anthropic API key (stub if empty) |
| `backend.secrets.openaiApiKey` | string | `""` | OpenAI key (Whisper stub if empty) |
| `backend.secrets.sentryDsn` | string | `""` | Sentry DSN |
| `bundledDatabase` | bool | `true` | Deploy bundled Postgres |
| `bundledRedis` | bool | `true` | Deploy bundled Redis |
| `ingress.hosts[0].host` | string | `spm.example.com` | Public hostname |
| `ingress.className` | string | `nginx` | Ingress class |

## Production example (`values.prod.yaml`)

```yaml
bundledDatabase: false   # use RDS / Cloud SQL
bundledRedis: false      # use ElastiCache / Memorystore

backend:
  replicaCount: 4
  autoscaling:
    minReplicas: 4
    maxReplicas: 20
  persistence:
    enabled: true
    storageClass: gp3
    size: 100Gi

ingress:
  className: nginx
  hosts:
    - host: spm.example.com
      paths:
        - path: /api
          service: backend
        - path: /ws
          service: backend
        - path: /
          service: frontend
  tls:
    - hosts: [spm.example.com]
      secretName: spm-tls-prod

backend:
  env:
    corsOrigins: "https://spm.example.com"
    sentryEnv: "production"
    otelExporterOtlpEndpoint: "http://otel-collector:4317"
```

## Uninstall

```bash
helm uninstall smart-pm --namespace smart-pm
```

PVCs and Secrets are not removed automatically; delete them with
`kubectl delete pvc,secret -n smart-pm -l app.kubernetes.io/instance=smart-pm`.
