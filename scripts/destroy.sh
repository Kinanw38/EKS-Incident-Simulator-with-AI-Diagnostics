#!/usr/bin/env bash
set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

echo -e "${RED}=================================================="${NC}
echo -e "${RED}⚠️  AI Incident Simulator: Infrastructure Teardown"${NC}
echo -e "${RED}=================================================="${NC}

read -p "Are you sure you want to PERMANENTLY DESTROY all AWS resources? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Teardown aborted."
  exit 0
fi

# 1. K8s Workload Cleanup to avoid hanging ELBs/ENIs
echo -e "\n🧹 Step 1/2: Cleaning Kubernetes workloads to release AWS Elastic Load Balancers & ENIs..."
if kubectl get nodes &> /dev/null; then
  kubectl delete deployments,services,pods,configmaps,secrets --all --all-namespaces --ignore-not-found=true || true
  echo "⏳ Waiting 20 seconds for AWS ENIs and Load Balancers to fully detach..."
  sleep 20
else
  echo "⚠️ Unable to query cluster via kubectl. Proceeding directly to Terraform destroy..."
fi

# 2. Terraform Destroy
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TERRAFORM_DIR="$SCRIPT_DIR/../terraform"

echo -e "\n💥 Step 2/2: Executing Terraform Destroy..."
cd "$TERRAFORM_DIR"
terraform destroy -auto-approve

echo -e "\n${GREEN}=================================================="${NC}
echo -e "${GREEN}✅ Teardown Complete! All AWS infrastructure removed safely."${NC}
echo -e "${GREEN}=================================================="${NC}