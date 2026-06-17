# Smart Student Project Manager — Kubernetes manifests

Production-ready K8s deployment for the Smart Student Project Manager
app.  All resources are namespaced under ``smart-pm``.

## Layout

```
k8s/
  00-namespace.yaml          # Namespace + default service account
  10-config.yaml             # ConfigMap + Secrets (placeholder values)
  20-postgres.yaml           # StatefulSet + Service + PVC
  30-redis.yaml              # Deployment + Service
  40-backend.yaml            # Deployment + Service (FastAPI)
  50-celery.yaml             # Deployment (Celery worker)
  60-frontend.yaml           # Deployment + Service (Next.js)
  70-ingress.yaml            # NGINX ingress + TLS
  80-hpa.yaml                # HorizontalPodAutoscaler
  90-network-policies.yaml   # NetworkPolicies (hardening)
```

## Quick start (kind / minikube)

```bash
# 1. Create the secret values (replace placeholders first)
kubectl apply -f 00-namespace.yaml
kubectl -n smart-pm create secret generic app-secrets \
  --from-literal=jwt-secret=CHANGE-ME \
  --from-literal=postgres-password=CHANGE-ME \
  --from-literal=anthropic-api-key= \
  --from-literal=openai-api-key= \
  --from-literal=sentry-dsn= \
  --dry-run=client -o yaml | kubectl apply -f -

# 2. Apply everything
kubectl apply -f .

# 3. Wait for pods
kubectl -n smart-pm get pods -w

# 4. Run Alembic migration once (job)
kubectl -n smart-pm create job manual-migrate \
  --image=ghcr.io/your-org/spm-backend:latest -- python -m alembic upgrade head

# 5. Port-forward
kubectl -n smart-pm port-forward svc/frontend 3000:80
```

In production set up an external managed Postgres + Redis (e.g. RDS /
ElastiCache) and remove the StatefulSet/Deployment for those.
