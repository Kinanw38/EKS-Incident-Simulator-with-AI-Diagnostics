#!/usr/bin/env bash
set -euo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}=================================================="${NC}
echo -e "${GREEN}🚀 AI Incident Simulator: Provisioning Infrastructure"${NC}
echo -e "${GREEN}=================================================="${NC}

# 1. Verification of CLI tools
echo "🔍 Checking local requirements..."
for cmd in terraform aws kubectl; do
  if ! command -v $cmd &> /dev/null; then
    echo -e "${RED}❌ Error: Command '$cmd' is not installed or not in PATH.${NC}"
    exit 1
  fi
done
echo "✅ All CLI tools (terraform, aws, kubectl) are present."

# 2. Terraform Apply
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

echo -e "\n📦 Provisioning VPC & EKS Cluster via Terraform..."
cd "$TERRAFORM_DIR"
terraform init
terraform apply -auto-approve

# 3. Fetch outputs
CLUSTER_NAME=$(terraform output -raw cluster_name)
AWS_REGION=$(terraform output -raw cluster_region)

echo -e "\n🔗 Updating local kubeconfig for EKS Cluster: ${YELLOW}${CLUSTER_NAME}${NC}..."
aws eks update-kubeconfig --region "$AWS_REGION" --name "$CLUSTER_NAME"

# 4. Wait for Control Plane readiness
echo -e "\n🩺 Validating Kubernetes Control Plane Connectivity..."
ATTEMPTS=0
MAX_ATTEMPTS=15

until kubectl get nodes &> /dev/null; do
  ATTEMPTS=$((ATTEMPTS+1))
  if [ $ATTEMPTS -eq $MAX_ATTEMPTS ]; then
    echo -e "${RED}❌ Error: Timed out waiting for Kubernetes API server to accept queries.${NC}"
    exit 1
  fi
  echo "⏳ Control Plane stabilizing... retrying in 10s ($ATTEMPTS/$MAX_ATTEMPTS)"
  sleep 10
done

echo -e "\n${GREEN}=================================================="${NC}
echo -e "${GREEN}✅ Infrastructure Provisioning Complete!"${NC}
echo -e "Cluster Name: ${CLUSTER_NAME}"
echo -e "Region:       ${AWS_REGION}"
echo -e "Node Count:   $(kubectl get nodes --no-headers | wc -l)"
echo -e "${GREEN}=================================================="${NC}