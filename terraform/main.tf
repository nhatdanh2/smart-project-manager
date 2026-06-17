terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.40"
    }
  }

  # Uncomment to bootstrap a remote state bucket via the same
  # provider, then re-init with:
  #   terraform init -backend-config=...
  # backend "s3" {
  #   bucket         = "spm-terraform-state"
  #   key            = "prod/terraform.tfstate"
  #   region         = "ap-southeast-1"
  #   dynamodb_table = "spm-terraform-locks"
  #   encrypt        = true
  # }
}

provider "aws" {
  region = var.aws_region
  default_tags {
    tags = {
      Project     = "smart-project-manager"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# Secondary region for cross-region replication (DR).
provider "aws" {
  alias  = "secondary"
  region = var.replica_region
  default_tags {
    tags = {
      Project     = "smart-project-manager"
      Environment = var.environment
      ManagedBy   = "terraform"
      Role        = "replica"
    }
  }
}

# -----------------------------------------------------------------------------
# Networking — minimal public+private VPC across 2 AZs
# -----------------------------------------------------------------------------
module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.5"

  name = "${var.project_name}-${var.environment}-vpc"
  cidr = "10.0.0.0/16"

  azs             = ["${var.aws_region}a", "${var.aws_region}b"]
  public_subnets  = ["10.0.1.0/24", "10.0.2.0/24"]
  private_subnets = ["10.0.10.0/24", "10.0.11.0/24"]

  enable_nat_gateway   = true
  single_nat_gateway   = var.environment != "production"
  enable_dns_hostnames = true
  enable_dns_support   = true

  tags = { "kubernetes.io/cluster/${var.cluster_name}" = "shared" }
}

# -----------------------------------------------------------------------------
# EKS — managed Kubernetes
# -----------------------------------------------------------------------------
module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.0"

  cluster_name    = var.cluster_name
  cluster_version = "1.29"
  vpc_id          = module.vpc.vpc_id
  subnet_ids      = module.vpc.private_subnets

  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  # IRSA (IAM Roles for Service Accounts) — required for the AWS
  # Load Balancer Controller and the cluster autoscaler.
  cluster_identity_providers = {
    sts = {
      client_identity = {
        sts = {
          audience = ["sts.amazonaws.com"]
        }
      }
    }
  }

  eks_managed_node_groups = {
    # General-purpose nodes for the API + Celery workers
    main = {
      min_size       = 2
      max_size       = 10
      desired_size   = 3
      instance_types = ["t3.large", "t3.xlarge"]
      capacity_type  = "ON_DEMAND"
      subnet_ids     = module.vpc.private_subnets

      k8s_labels = { role = "general" }
    }
    # Spot instances for the frontend (stateless, cheap to evict)
    spot = {
      min_size       = 1
      max_size       = 5
      desired_size   = 2
      instance_types = ["t3.medium", "t3a.medium", "t4g.medium"]
      capacity_type  = "SPOT"
      subnet_ids     = module.vpc.private_subnets

      k8s_labels = { role = "spot-frontend" }
    }
  }

  # EKS add-ons
  cluster_addons = {
    coredns = { most_recent = true }
    kube-proxy = { most_recent = true }
    vpc-cni = { most_recent = true }
    aws-ebs-csi-driver = { most_recent = true }
  }

  tags = { "k8s.io/cluster-autoscaler/enabled" = "true" }
}

# -----------------------------------------------------------------------------
# RDS Postgres (multi-AZ in prod, single-AZ in staging)
# -----------------------------------------------------------------------------
resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-db"
  subnet_ids = module.vpc.private_subnets

  tags = { Name = "${var.project_name}-${var.environment}-db-subnets" }
}

resource "aws_security_group" "rds" {
  name   = "${var.project_name}-${var.environment}-rds"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
    description     = "Postgres from EKS nodes"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { Name = "${var.project_name}-${var.environment}-rds-sg" }
}

resource "aws_db_instance" "postgres" {
  identifier              = "${var.project_name}-${var.environment}-pg"
  engine                  = "postgres"
  engine_version          = "16.3"
  instance_class          = var.environment == "production" ? "db.t3.medium" : "db.t3.micro"
  allocated_storage       = 20
  max_allocated_storage   = 200
  storage_type            = "gp3"
  storage_encrypted       = true
  multi_az                = var.environment == "production"
  db_name                 = "spm"
  username                = "spm"
  password                = var.db_password
  db_subnet_group_name    = aws_db_subnet_group.main.name
  vpc_security_group_ids  = [aws_security_group.rds.id]
  backup_retention_period = var.environment == "production" ? 14 : 7
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:00:00-Mon:03:00"
  skip_final_snapshot     = var.environment != "production"
  deletion_protection     = var.environment == "production"

  performance_insights_enabled = true
  performance_insights_retention_period = 7
}

# -----------------------------------------------------------------------------
# ElastiCache Redis
# -----------------------------------------------------------------------------
resource "aws_elasticache_subnet_group" "main" {
  name       = "${var.project_name}-${var.environment}-cache"
  subnet_ids = module.vpc.private_subnets
}

resource "aws_security_group" "redis" {
  name   = "${var.project_name}-${var.environment}-redis"
  vpc_id = module.vpc.vpc_id

  ingress {
    from_port       = 6379
    to_port         = 6379
    protocol        = "tcp"
    security_groups = [module.eks.cluster_security_group_id]
    description     = "Redis from EKS nodes"
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "${var.project_name}-${var.environment}-redis"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = "cache.t3.micro"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  port                 = 6379
  subnet_group_name    = aws_elasticache_subnet_group.main.name
  security_group_ids   = [aws_security_group.redis.id]

  at_rest_encryption_enabled = true
  transit_encryption_enabled = true
  auth_token                 = var.redis_auth_token

  snapshot_retention_limit = 5
  snapshot_window          = "05:00-07:00"
}

# -----------------------------------------------------------------------------
# S3 — file uploads (fronted by the file router with presigned URLs
# in a future phase; for now it's just durable storage for the
# monthly backups).
# -----------------------------------------------------------------------------
resource "aws_s3_bucket" "uploads" {
  bucket = "${var.project_name}-${var.environment}-uploads-${data.aws_caller_identity.current.account_id}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "uploads" {
  bucket                  = aws_s3_bucket.uploads.id
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# -----------------------------------------------------------------------------
# Phase 14: lifecycle + cross-region replication
# -----------------------------------------------------------------------------
# Move objects to Glacier 90 days after upload, then expire 7 years
# after upload (industry-standard retention for student work).  This
# is applied to the *whole* bucket; for stricter retention use
# object-lock on a separate bucket.
# -----------------------------------------------------------------------------
resource "aws_s3_bucket_lifecycle_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id

  rule {
    id     = "tier-to-glacier-then-expire"
    status = "Enabled"

    # Apply to everything by default
    filter {}

    transition {
      days          = 90
      storage_class = "GLACIER"
    }
    transition {
      days          = 365
      storage_class = "DEEP_ARCHIVE"
    }
    expiration {
      days = 7 * 365  # 7 years
    }
    noncurrent_version_expiration {
      noncurrent_days = 30
    }
    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }

  rule {
    id     = "expire-tmp"
    status = "Enabled"

    # Files uploaded to /tmp/ are short-lived artifacts (AI
    # extraction, Whisper transcription).  Drop them after 24h.
    filter {
      prefix = "tmp/"
    }
    expiration {
      days = 1
    }
  }
}

# -----------------------------------------------------------------------------
# Cross-region replication (CRR) to a second region for DR.
# We provision a *replica* bucket in the secondary region plus an
# IAM role the source bucket assumes to copy objects.
# -----------------------------------------------------------------------------
resource "aws_s3_bucket" "uploads_replica" {
  provider = aws.secondary
  bucket   = "${var.project_name}-${var.environment}-uploads-replica-${data.aws_caller_identity.current.account_id}"

  lifecycle {
    prevent_destroy = true
  }
}

resource "aws_s3_bucket_versioning" "uploads_replica" {
  provider = aws.secondary
  bucket   = aws_s3_bucket.uploads_replica.id
  versioning_configuration { status = "Enabled" }
}

resource "aws_iam_role" "crr" {
  name = "${var.project_name}-${var.environment}-s3-crr"

  assume_role_policy = jsonencode({
    Version = "2012-10-17",
    Statement = [{
      Effect = "Allow",
      Principal = { Service = "s3.amazonaws.com" },
      Action = "sts:AssumeRole",
    }],
  })
}

resource "aws_iam_role_policy" "crr" {
  name = "crr"
  role = aws_iam_role.crr.id

  policy = jsonencode({
    Version = "2012-10-17",
    Statement = [
      {
        Effect = "Allow",
        Action = [
          "s3:GetReplicationConfiguration",
          "s3:ListBucket",
        ],
        Resource = aws_s3_bucket.uploads.arn,
      },
      {
        Effect = "Allow",
        Action = [
          "s3:GetObjectVersionForReplication",
          "s3:GetObjectVersionAcl",
          "s3:GetObjectVersionTagging",
        ],
        Resource = "${aws_s3_bucket.uploads.arn}/*",
      },
      {
        Effect = "Allow",
        Action = [
          "s3:ReplicateObject",
          "s3:ReplicateDelete",
          "s3:ReplicateTags",
        ],
        Resource = "${aws_s3_bucket.uploads_replica.arn}/*",
      },
    ],
  })
}

resource "aws_s3_bucket_replication_configuration" "uploads" {
  bucket = aws_s3_bucket.uploads.id
  role   = aws_iam_role.crr.arn

  rule {
    id     = "crr-all"
    status = "Enabled"
    filter {}

    delete_marker_replication { status = "Enabled" }

    destination {
      bucket        = aws_s3_bucket.uploads_replica.arn
      storage_class = "STANDARD_IA"
    }
  }

  # Replication config requires versioning; we enabled it above
  depends_on = [aws_s3_bucket_versioning.uploads]
}

# -----------------------------------------------------------------------------
# ALB + TLS — public ingress
# -----------------------------------------------------------------------------
data "aws_caller_identity" "current" {}

resource "aws_acm_certificate" "main" {
  domain_name       = var.domain_name
  validation_method = "DNS"

  lifecycle {
    create_before_destroy = true
  }
}

# (Route53 record creation is left as an exercise — the validation
# records need to be created before the certificate becomes valid.)

# -----------------------------------------------------------------------------
# Outputs
# -----------------------------------------------------------------------------
output "cluster_name" {
  value = module.eks.cluster_name
}

output "cluster_endpoint" {
  value = module.eks.cluster_endpoint
}

output "db_endpoint" {
  value     = aws_db_instance.postgres.endpoint
  sensitive = true
}

output "redis_endpoint" {
  value     = aws_elasticache_cluster.redis.cache_nodes[0].address
  sensitive = true
}

output "s3_uploads_bucket" {
  value = aws_s3_bucket.uploads.bucket
}
