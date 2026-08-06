# Networking targets for the API load balancer.

resource "aws_security_group" "api" {
  name        = "conductor-api"
  description = "Allow HTTPS and health-check traffic to the API ALB"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_lb_target_group" "api" {
  name        = "conductor-api"
  port        = 8000
  protocol    = "HTTP"
  vpc_id      = data.aws_vpc.default.id
  target_type = "ip"

  health_check {
    path                = "/api/v1/health/ready"
    interval            = 30
    timeout             = 5
    healthy_threshold   = 3
    unhealthy_threshold = 3
  }
}

resource "aws_elasticache_subnet_group" "conductor" {
  name       = "conductor-cache-subnet"
  subnet_ids = [for s in data.aws_subnets.default : s.id]
}