# Core Conductor infrastructure (docs/13-deployment.md).
terraform {
  required_version = ">= 1.5"
  required_providers {
    aws = { source = "hashicorp/aws", version = "~> 5.0" }
  }
  backend "s3" {
    bucket         = "conductor-tfstate"
    key            = "prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "conductor-tfstate-lock"
  }
}

provider "aws" {
  region = var.region
}

data "aws_caller_identity" "current" {}

variable "region" {
  default = "us-east-1"
}

variable "environment" {
  default = "prod"
}

data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

# Document storage
resource "aws_s3_bucket" "documents" {
  bucket        = "conductor-${var.environment}-documents"
  force_destroy = false
}

resource "aws_s3_bucket_versioning" "documents" {
  bucket = aws_s3_bucket.documents.id
  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "documents" {
  bucket = aws_s3_bucket.documents.id
  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "aws:kms"
    }
  }
}

# Container registry
resource "aws_ecr_repository" "backend" {
  name = "conductor/backend"
}
resource "aws_ecr_repository" "worker" {
  name = "conductor/worker"
}
resource "aws_ecr_repository" "frontend" {
  name = "conductor/frontend"
}

# PostgreSQL
resource "aws_db_instance" "postgres" {
  identifier             = "conductor-${var.environment}"
  engine                 = "postgres"
  engine_version         = "16.3"
  instance_class         = "db.t4g.large"
  allocated_storage      = 50
  multi_az               = var.environment == "prod"
  db_name                = "conductor"
  username               = "conductor"
  password               = var.db_password
  skip_final_snapshot    = false
  final_snapshot_identifier = "conductor-${var.environment}-final"
  backup_retention_period = 14
  storage_encrypted      = true
}

# ElastiCache Redis (rate limits, cache, Celery broker)
resource "aws_elasticache_cluster" "redis" {
  cluster_id           = "conductor-${var.environment}"
  engine               = "redis"
  engine_version       = "7.1"
  node_type            = "cache.t4g.small"
  num_cache_nodes      = 1
  parameter_group_name = "default.redis7"
  subnet_group_name    = "conductor-cache-subnet"
}

variable "db_password" {}
variable "db_username" {
  default = "conductor"
}

# Compute: ECS Fargate service + autoscaling
resource "aws_ecs_cluster" "conductor" {
  name = "conductor-${var.environment}"
}

resource "aws_ecs_task_definition" "backend" {
  family                   = "conductor-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = "1024"
  memory                   = "2048"
  execution_role_arn       = aws_iam_role.ecs_execution.arn
  task_role_arn            = aws_iam_role.ecs_task.arn
  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = "${aws_ecr_repository.backend.repository_url}:latest"
      essential = true
      portMappings = [{ containerPort = 8000, protocol = "tcp" }]
      environment = [
        { name = "DATABASE_URL", value = "postgresql+psycopg://${var.db_username}:${var.db_password}@${aws_db_instance.postgres.address}/conductor" },
        { name = "REDIS_URL", value = "redis://${aws_elasticache_cluster.redis.endpoint}" },
        { name = "APP_ENV", value = var.environment },
      ]
      logConfiguration = {
        logDriver = "awslogs"
        options = { "awslogs-group" = "/conductor/backend", "awslogs-region" = var.region }
      }
    }
  ])
}

resource "aws_lb" "api" {
  name               = "conductor-api-${var.environment}"
  internal           = false
  security_groups    = [aws_security_group.api.id]
  subnet_ids         = [for s in data.aws_subnets.default : s.id]
  enable_deletion_protection = var.environment == "production"
}

resource "aws_lb_listener" "api" {
  load_balancer_arn = aws_lb.api.id
  port              = 443
  protocol          = "HTTPS"
  certificate_arn   = var.acm_certificate_arn
  default_action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.api.id
  }
}

# IAM roles (docs/12-security.md)
resource "aws_iam_role" "ecs_execution" {
  name = "conductor-ecs-execution"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{ Effect = "Allow", Principal = { Service = "ecs-tasks.amazonaws.com" }, Action = "sts:AssumeRole" }]
  })
}

variable "acm_certificate_arn" {
  description = "ACM TLS certificate ARN for the API ALB"
}