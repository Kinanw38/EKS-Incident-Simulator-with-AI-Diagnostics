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