output "cluster_name" {
  description = "EKS Cluster Name"
  value       = aws_eks_cluster.main.name
}

output "cluster_region" {
  description = "AWS Region of the deployed cluster"
  value       = var.aws_region
}

output "cluster_endpoint" {
  description = "EKS API Server Endpoint"
  value       = aws_eks_cluster.main.endpoint
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}

output "private_subnets" {
  description = "List of Private Subnet IDs"
  value       = aws_subnet.private[*].id
}

output "public_subnets" {
  description = "List of Public Subnet IDs"
  value       = aws_subnet.public[*].id
}