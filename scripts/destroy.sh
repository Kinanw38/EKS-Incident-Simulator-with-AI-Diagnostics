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

stop_process_group() {
  local pid_file="$1"
  local name="$2"

  if [[ -f "$pid_file" ]]; then
    local pid
    pid="$(cat "$pid_file" 2>/dev/null || true)"

    if [[ -n "$pid" ]] && kill -0 "$pid" >/dev/null 2>&1; then
      echo "Stopping local $name (Process Group $pid)..."

      # 1. ניסיון סגירה מנומס (SIGTERM) לכל עץ התהליכים
      kill -15 -- "-$pid" 2>/dev/null || kill -15 "$pid" 2>/dev/null || true
      sleep 1

      # 2. אם התהליך עדיין חי - חיסול מיידי (SIGKILL)
      if kill -0 "$pid" >/dev/null 2>&1; then
        kill -9 -- "-$pid" 2>/dev/null || kill -9 "$pid" 2>/dev/null || true
      fi
    fi
    rm -f "$pid_file"
  fi
}

stop_local_services() {
  stop_process_group "$BACKEND_PID_FILE" "backend"
  stop_process_group "$FRONTEND_PID_FILE" "frontend"
}

echo -e "\n🧹 Step 1/3: Stopping local services..."
stop_local_services

echo -e "\n🧹 Step 2/3: Cleaning Kubernetes workloads to release AWS dependencies..."
if kubectl get nodes &> /dev/null; then
  kubectl delete deployments,statefulsets,daemonsets,services,ingress,pods,configmaps,secrets --all --all-namespaces --ignore-not-found=true || true

  echo "⏳ Waiting 45 seconds for AWS VPC CNI and Load Balancers to release Subnet ENIs..."
  for ((i=45; i>0; i--)); do
    echo -ne "   Time remaining: ${i}s...\r"
    sleep 1
  done
  echo -e "\n✅ ENI release wait period complete. Proceeding to Terraform destroy."
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