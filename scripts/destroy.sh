#!/usr/bin/env bash
set -Eeuo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.logs"
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

echo -e "${RED}==================================================${NC}"
echo -e "${RED}⚠️  AI Incident Simulator: Infrastructure Teardown${NC}"
echo -e "${RED}==================================================${NC}"

read -p "Are you sure you want to PERMANENTLY DESTROY all AWS resources? (y/N) " -n 1 -r
echo
if [[ ! $REPLY =~ ^[Yy]$ ]]; then
  echo "Teardown aborted."
  exit 0
fi

stop_local_services() {
  if [[ -f "$BACKEND_PID_FILE" ]]; then
    local pid
    pid="$(cat "$BACKEND_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "Stopping local backend..."
      kill "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "$BACKEND_PID_FILE"
  fi

  if [[ -f "$FRONTEND_PID_FILE" ]]; then
    local pid
    pid="$(cat "$FRONTEND_PID_FILE" 2>/dev/null || true)"
    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "Stopping local frontend..."
      kill "$pid" >/dev/null 2>&1 || true
    fi
    rm -f "$FRONTEND_PID_FILE"
  fi
}

echo -e "\n🧹 Step 1/3: Stopping local services..."
stop_local_services

echo -e "\n🧹 Step 2/3: Cleaning Kubernetes workloads to release AWS dependencies..."
if kubectl get nodes &> /dev/null; then
  kubectl delete deployments,services,pods,configmaps,secrets --all --all-namespaces --ignore-not-found=true || true
  echo "⏳ Waiting for AWS resources to detach..."
  sleep 20
else
  echo "⚠️ Unable to query cluster via kubectl. Proceeding directly to Terraform destroy..."
fi

echo -e "\n💥 Step 3/3: Executing Terraform Destroy..."
cd "$TERRAFORM_DIR"

terraform destroy -auto-approve || {
  echo -e "${YELLOW}Terraform destroy reported a dependency problem.${NC}"
  echo "Checking for leftover AWS resources blocking VPC deletion..."
  aws ec2 describe-network-interfaces \
    --region "$(terraform output -raw cluster_region 2>/dev/null || aws configure get region || echo us-east-1)" \
    --filters Name=vpc-id,Values="$(terraform output -raw vpc_id 2>/dev/null || true)" \
    --query 'NetworkInterfaces[*].{ID:NetworkInterfaceId,Status:Status,Description:Description}' \
    --output table || true

  aws ec2 describe-security-groups \
    --region "$(terraform output -raw cluster_region 2>/dev/null || aws configure get region || echo us-east-1)" \
    --filters Name=vpc-id,Values="$(terraform output -raw vpc_id 2>/dev/null || true)" \
    --query 'SecurityGroups[*].{ID:GroupId,Name:GroupName}' \
    --output table || true

  echo "If the VPC is still in deleting state, wait a few minutes and rerun:"
  echo "  ./scripts/destroy.sh"
  exit 1
}

echo -e "\n${GREEN}==================================================${NC}"
echo -e "${GREEN}✅ Teardown Complete! All AWS infrastructure removed safely.${NC}"
echo -e "${GREEN}==================================================${NC}"