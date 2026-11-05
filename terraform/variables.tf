variable "aws_region" {
  description = "AWS Region for resource deployment"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment tag (e.g., dev, staging, prod)"
  type        = string
  default     = "dev"
}

variable "cluster_name" {
  description = "Name of the EKS Cluster"
  type        = string
  default     = "incident-sim-cluster"
}

variable "kubernetes_version" {
  description = "EKS Kubernetes version. Keep it in STANDARD support: older versions move to extended support, which costs $0.60/h instead of $0.10/h for the control plane. Check: aws eks describe-cluster-versions --region us-east-1"
  type        = string
  default     = "1.35"

  validation {
    condition     = can(regex("^1\\.[0-9]+$", var.kubernetes_version))
    error_message = "Use a version like \"1.35\" (major.minor, no patch)."
  }
}

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "node_instance_types" {
  description = "EC2 Instance types for EKS Worker Nodes"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "desired_capacity" {
  description = "Desired capacity for the EKS Node Group"
  type        = number
  default     = 2

  validation {
    condition     = var.desired_capacity >= var.min_capacity && var.desired_capacity <= var.max_capacity
    error_message = "Node group sizes must satisfy min_capacity <= desired_capacity <= max_capacity."
  }
}

variable "max_capacity" {
  description = "Maximum capacity for the EKS Node Group"
  type        = number
  default     = 3
}

variable "min_capacity" {
  description = "Minimum capacity for the EKS Node Group"
  type        = number
  default     = 1
}

variable "public_access_cidrs" {
  description = "CIDR blocks allowed to reach the public EKS API endpoint. There is deliberately NO default: a default of 0.0.0.0/0 would silently expose the endpoint to the whole internet. scripts/setup.sh detects your public address range and passes it in; use 0.0.0.0/0 only on purpose."
  type        = list(string)

  validation {
    condition     = length(var.public_access_cidrs) > 0 && alltrue([for cidr in var.public_access_cidrs : can(cidrhost(cidr, 0))])
    error_message = "Provide at least one valid CIDR block, for example 203.0.113.7/32."
  }
}
