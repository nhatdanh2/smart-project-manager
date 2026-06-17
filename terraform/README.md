# Terraform — Smart PM infrastructure

Provisions the cloud infrastructure for the Smart Student Project
Manager on AWS:

* **VPC** across 2 AZs (public + private subnets, NAT gateway)
* **EKS** managed Kubernetes with a system pool + spot pool for the
  frontend
* **RDS Postgres 16** (gp3 storage, Multi-AZ in production, automated
  backups, Performance Insights)
* **ElastiCache Redis 7** with encryption at rest + transit
* **S3** for durable file uploads
* **ACM** certificate (DNS-validated) ready for the ALB

## Quick start

```bash
# 1. Configure AWS credentials (or use SSO)
aws configure sso

# 2. Bootstrap a state bucket (one-time)
# See the commented ``backend "s3"`` block in main.tf.

# 3. Initialise
terraform init

# 4. Plan
terraform plan -out=tfplan

# 5. Apply
terraform apply tfplan

# 6. Configure kubectl
aws eks update-kubeconfig --region ap-southeast-1 --name spm-cluster
```

## Production rollout

The chart is deployed by the `deploy` GitHub Actions workflow
(`.github/workflows/deploy.yml`) on every release.  Configure the
following GitHub Environment secrets:

| Secret | Description |
| --- | --- |
| ``KUBECONFIG`` | Base64-encoded kubeconfig for the target cluster |
| ``JWT_SECRET_KEY`` | 32-byte random hex |
| ``POSTGRES_PASSWORD`` | Same value as ``TF_VAR_db_password`` |
| ``ANTHROPIC_API_KEY`` | AI advisor |
| ``OPENAI_API_KEY`` | Whisper transcription |
| ``SENTRY_DSN`` | Optional error tracking |

## Cost (rough monthly, ap-southeast-1)

| Resource | Estimate |
| --- | --- |
| EKS control plane | $73 |
| 3× t3.large API nodes | $115 |
| 2× t3.medium spot frontend | $25 |
| db.t3.medium Multi-AZ RDS | $140 |
| cache.t3.micro Redis | $15 |
| NAT gateway + data | $35 |
| ALB | $20 |
| S3 + misc | $10 |
| **Total** | **~$430/mo** |

Single-AZ staging can be cut roughly in half by setting
``environment = "staging"`` and using ``db.t3.micro`` / a single
NAT gateway.

## Destroying the stack

```bash
terraform destroy
```

RDS has ``deletion_protection = true`` in production — flip that off
in the console first if you really mean it.
