#!/usr/bin/env bash
#
# Tears down everything setup.sh created, and then CHECKS that nothing is
# left behind (leftovers keep costing money).
#
# Usage: ./scripts/destroy.sh [--yes]
#
# It never touches your current kubectl context: it builds its own temporary
# kubeconfig for the cluster that Terraform knows about.
set -Eeuo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG_DIR="$PROJECT_ROOT/.logs"
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

# Label that every simulator manifest carries (see scenarios.py and k8s/*.yaml).
SIM_LABEL="app.kubernetes.io/part-of=incident-simulator"
PROJECT_TAG_KEY="Project"
PROJECT_TAG_VALUE="AI-Incident-Simulator"

TOTAL_STEPS=7
ASSUME_YES=false
TMP_KUBECONFIG=""

for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=true ;;
    -h|--help)
      echo "Usage: ./scripts/destroy.sh [--yes]"
      echo "  --yes  do not ask for confirmation"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

print_error() { echo -e "${RED}❌ $1${NC}" >&2; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }

step() {
  echo
  echo -e "${BLUE}━━━ Step $1/${TOTAL_STEPS}: $2 ━━━${NC}"
  echo "    $3"
}

on_exit() {
  if [[ -n "$TMP_KUBECONFIG" ]]; then
    rm -f "$TMP_KUBECONFIG"
  fi
}
trap on_exit EXIT

CURRENT_PHASE="starting"
on_error() {
  print_error "Teardown stopped unexpectedly during: ${CURRENT_PHASE}."
  echo "It is safe to run ./scripts/destroy.sh again."
}
trap on_error ERR

# --------------------------------------------------------------------------
# Step 1: find out what we are about to destroy (nothing is deleted yet)
# --------------------------------------------------------------------------
CURRENT_PHASE="reading Terraform outputs"
echo -e "${RED}==================================================${NC}"
echo -e "${RED}⚠️  AI Incident Simulator: Infrastructure Teardown${NC}"
echo -e "${RED}==================================================${NC}"

step 1 "Finding what will be destroyed" "Reads the cluster name and region from Terraform, not from your kubectl context."

CLUSTER_NAME=""
AWS_REGION_VALUE=""
VPC_ID=""
if [[ -d "$TERRAFORM_DIR/.terraform" ]]; then
  CLUSTER_NAME="$(cd "$TERRAFORM_DIR" && terraform output -raw cluster_name 2>/dev/null || true)"
  AWS_REGION_VALUE="$(cd "$TERRAFORM_DIR" && terraform output -raw cluster_region 2>/dev/null || true)"
  VPC_ID="$(cd "$TERRAFORM_DIR" && terraform output -raw vpc_id 2>/dev/null || true)"
fi
AWS_REGION_VALUE="${AWS_REGION_VALUE:-${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || true)}}}"
AWS_REGION_VALUE="${AWS_REGION_VALUE:-us-east-1}"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null || echo unknown)"

echo "  AWS account: $ACCOUNT_ID"
echo "  Region:      $AWS_REGION_VALUE"
echo "  Cluster:     ${CLUSTER_NAME:-<not found in Terraform state>}"
echo "  VPC:         ${VPC_ID:-<not found in Terraform state>}"

if [[ "$ASSUME_YES" != "true" ]]; then
  echo
  read -r -p "PERMANENTLY DESTROY these AWS resources? (y/N) " -n 1 REPLY
  echo
  if [[ ! "$REPLY" =~ ^[Yy]$ ]]; then
    echo "Teardown aborted. Nothing was deleted."
    exit 0
  fi
fi

# --------------------------------------------------------------------------
# Step 2: stop the local backend and frontend
# --------------------------------------------------------------------------
stop_process_group() {
  local pid_file="$1"
  local name="$2"

  if [[ -f "$pid_file" ]]; then
    local pgid
    pgid="$(cat "$pid_file" 2>/dev/null || true)"

    if [[ "$pgid" =~ ^[0-9]+$ ]] && kill -0 "$pgid" >/dev/null 2>&1; then
      echo "  Stopping local $name (process group $pgid)..."
      # Polite stop (SIGTERM) for the whole process tree, then force if needed.
      kill -15 -- "-$pgid" 2>/dev/null || kill -15 "$pgid" 2>/dev/null || true
      sleep 1
      if kill -0 "$pgid" >/dev/null 2>&1; then
        kill -9 -- "-$pgid" 2>/dev/null || kill -9 "$pgid" 2>/dev/null || true
      fi
    fi
    rm -f "$pid_file"
  fi
}

port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

CURRENT_PHASE="stopping local services"
step 2 "Stopping the local app" "Stops the backend and the dashboard on this machine (process groups, so no orphan keeps the port)."
stop_process_group "$BACKEND_PID_FILE" "backend"
stop_process_group "$FRONTEND_PID_FILE" "frontend"
sleep 1
for port in "$BACKEND_PORT" "$FRONTEND_PORT"; do
  if port_in_use "$port"; then
    print_warning "Port $port is still in use by another program. Not killed automatically."
    echo "  Find it with: ss -ltnp | grep :$port"
  else
    print_success "Port $port is free."
  fi
done

# --------------------------------------------------------------------------
# Step 3: delete the simulator's Kubernetes resources (by label only)
# --------------------------------------------------------------------------
KUBE_REACHABLE=false
LB_SERVICES_FOUND=false

kc() { kubectl --kubeconfig "$TMP_KUBECONFIG" "$@"; }

list_lb_services() {
  kc get services --all-namespaces \
    -o jsonpath='{range .items[?(@.spec.type=="LoadBalancer")]}{.metadata.namespace}/{.metadata.name}{"\n"}{end}' \
    2>/dev/null || true
}

CURRENT_PHASE="cleaning Kubernetes resources"
step 3 "Cleaning Kubernetes resources" "A LoadBalancer Service creates an AWS load balancer that blocks VPC deletion, so it must go first."

if [[ -z "$CLUSTER_NAME" ]]; then
  print_warning "No cluster found in Terraform state. Skipping Kubernetes cleanup."
elif ! command -v kubectl >/dev/null 2>&1; then
  print_warning "kubectl not found. Skipping Kubernetes cleanup."
else
  TMP_KUBECONFIG="$(mktemp)"
  if aws eks update-kubeconfig --region "$AWS_REGION_VALUE" --name "$CLUSTER_NAME" \
      --kubeconfig "$TMP_KUBECONFIG" >/dev/null 2>&1 \
    && kc get nodes --request-timeout=20s >/dev/null 2>&1; then
    KUBE_REACHABLE=true
  fi

  if [[ "$KUBE_REACHABLE" != "true" ]]; then
    print_warning "Cannot reach the cluster API (is your IP different from when you ran setup.sh?)."
    echo "  Skipping Kubernetes cleanup and touching nothing else in the cluster."
    echo "  If Terraform later fails on the VPC, a load balancer may be left behind."
  else
    print_success "Cluster reachable (using a temporary kubeconfig, your current context is untouched)."

    LB_LIST="$(list_lb_services)"
    if [[ -n "$LB_LIST" ]]; then
      LB_SERVICES_FOUND=true
      echo "  Services of type LoadBalancer found (they own AWS load balancers):"
      while IFS= read -r lb_line; do echo "    - $lb_line"; done <<< "$LB_LIST"
      while IFS=/ read -r ns name; do
        [[ -n "$name" ]] && kc delete service "$name" -n "$ns" --ignore-not-found=true --wait=false || true
      done <<< "$LB_LIST"
    else
      echo "  No LoadBalancer services."
    fi

    echo "  Deleting simulator resources labelled $SIM_LABEL ..."
    kc delete deployments,statefulsets,daemonsets,services,ingress,pods,configmaps,secrets \
      --all-namespaces -l "$SIM_LABEL" --ignore-not-found=true || true
  fi
fi

# --------------------------------------------------------------------------
# Step 4: wait for load balancers to disappear (only if there were any)
# --------------------------------------------------------------------------
CURRENT_PHASE="waiting for load balancers"
step 4 "Waiting for AWS load balancers" "Only needed if LoadBalancer services existed. Checks every 10s, up to 3 minutes."
if [[ "$LB_SERVICES_FOUND" == "true" ]]; then
  waited=0
  while [[ -n "$(list_lb_services)" && $waited -lt 180 ]]; do
    echo "  Still deleting load balancers... (${waited}s)"
    sleep 10
    waited=$((waited + 10))
  done
  if [[ -n "$(list_lb_services)" ]]; then
    print_warning "A LoadBalancer service still exists after 3 minutes. Terraform may need a retry."
  else
    print_success "Load balancer services are gone."
  fi
else
  echo "  No load balancers to wait for. Skipping."
fi

# --------------------------------------------------------------------------
# Step 5: terraform destroy (up to 3 attempts)
# --------------------------------------------------------------------------
print_leftover_diagnostics() {
  local vpc="$VPC_ID"
  echo "Checking for leftover AWS resources blocking VPC deletion..."
  if [[ -z "$vpc" ]]; then
    echo "  VPC id unknown, skipping diagnostics."
    return 0
  fi
  aws ec2 describe-network-interfaces \
    --region "$AWS_REGION_VALUE" \
    --filters Name=vpc-id,Values="$vpc" \
    --query 'NetworkInterfaces[*].{ID:NetworkInterfaceId,Status:Status,Description:Description}' \
    --output table || true
  aws ec2 describe-security-groups \
    --region "$AWS_REGION_VALUE" \
    --filters Name=vpc-id,Values="$vpc" \
    --query 'SecurityGroups[*].{ID:GroupId,Name:GroupName}' \
    --output table || true
}

CURRENT_PHASE="terraform destroy"
step 5 "Destroying the AWS infrastructure with Terraform" "Takes about 10-15 minutes. A VPC error is often temporary, so it retries up to 3 times, 60s apart."
cd "$TERRAFORM_DIR"
destroyed=false
for attempt in 1 2 3; do
  echo "  Attempt $attempt/3"
  # public_access_cidrs has no default on purpose (see variables.tf). Its value
  # is irrelevant when destroying, but Terraform still needs one to load the config.
  if terraform destroy -auto-approve -var 'public_access_cidrs=["127.0.0.1/32"]'; then
    destroyed=true
    break
  fi
  if (( attempt < 3 )); then
    print_warning "terraform destroy failed (often a transient VPC DependencyViolation). Retrying in 60s..."
    sleep 60
  fi
done

if [[ "$destroyed" != "true" ]]; then
  print_error "terraform destroy failed 3 times."
  print_leftover_diagnostics
  echo "If the VPC is still in 'deleting' state, wait a few minutes and run again:"
  echo "  ./scripts/destroy.sh"
  exit 1
fi
print_success "Terraform destroy finished."

# --------------------------------------------------------------------------
# Step 6: verify that nothing is left behind
# --------------------------------------------------------------------------
FAILED=0
check() {
  # check "description" "count of leftovers" "hint"
  local description="$1"
  local count="$2"
  local hint="$3"
  if [[ "$count" == "0" ]]; then
    echo -e "  ${GREEN}PASS${NC}  $description"
  else
    echo -e "  ${RED}FAIL${NC}  $description ($count found). $hint"
    FAILED=1
  fi
}

CURRENT_PHASE="post-destroy verification"
step 6 "Verifying nothing is left behind" "Asks AWS directly. Leftovers keep costing money."

# The tag index lags behind reality: a resource that was just deleted can stay
# listed for a while (a deleted NAT gateway is even kept by EC2 for about an
# hour, with state "deleted"). So the check retries a few times, and ignores
# NAT gateways whose state is "deleted". Anything still listed is printed.
list_tagged_leftovers() {
  local arns arn state
  arns="$(aws resourcegroupstaggingapi get-resources --region "$AWS_REGION_VALUE" \
    --tag-filters "Key=${PROJECT_TAG_KEY},Values=${PROJECT_TAG_VALUE}" \
    --query 'ResourceTagMappingList[].ResourceARN' --output text 2>/dev/null)" || return 1

  for arn in $arns; do
    if [[ "$arn" == *":natgateway/"* ]]; then
      state="$(aws ec2 describe-nat-gateways --region "$AWS_REGION_VALUE" \
        --nat-gateway-ids "${arn##*/}" --query 'NatGateways[0].State' \
        --output text 2>/dev/null || echo unknown)"
      if [[ "$state" == "deleted" ]]; then
        continue
      fi
    fi
    echo "$arn"
  done
}

TAG_LEFTOVERS=""
tag_query_ok=true
for attempt in 1 2 3 4 5 6; do
  if ! TAG_LEFTOVERS="$(list_tagged_leftovers)"; then
    tag_query_ok=false
    break
  fi
  if [[ -z "$TAG_LEFTOVERS" ]]; then
    break
  fi
  if (( attempt < 6 )); then
    echo "  Tagged resources still listed (the index can lag). Checking again in 20s... ($attempt/6)"
    sleep 20
  fi
done

if [[ "$tag_query_ok" != "true" ]]; then
  echo -e "  ${YELLOW}SKIP${NC}  Tagged resources: the query failed (check your permissions)."
elif [[ -z "$TAG_LEFTOVERS" ]]; then
  echo -e "  ${GREEN}PASS${NC}  No resources tagged ${PROJECT_TAG_KEY}=${PROJECT_TAG_VALUE}"
else
  tagged_count="$(echo "$TAG_LEFTOVERS" | wc -l | tr -d ' ')"
  check "No resources tagged ${PROJECT_TAG_KEY}=${PROJECT_TAG_VALUE}" "$tagged_count" \
    "Still listed after a couple of minutes (the tag index can lag up to an hour)."
  while IFS= read -r leftover_arn; do
    echo "        - $leftover_arn"
  done <<< "$TAG_LEFTOVERS"
  echo "        Check one: aws resourcegroupstaggingapi get-resources --tag-filters Key=${PROJECT_TAG_KEY},Values=${PROJECT_TAG_VALUE}"
fi

if [[ -n "$CLUSTER_NAME" ]]; then
  cluster_left="$(aws eks list-clusters --region "$AWS_REGION_VALUE" \
    --query "length(clusters[?@=='${CLUSTER_NAME}'])" --output text 2>/dev/null || echo "?")"
  if [[ "$cluster_left" == "?" ]]; then
    echo -e "  ${YELLOW}SKIP${NC}  EKS cluster: the query failed."
  else
    check "EKS cluster '${CLUSTER_NAME}' is gone" "$cluster_left" "Check the EKS console."
  fi
fi

if [[ -n "$VPC_ID" ]]; then
  nat_filter="Name=vpc-id,Values=${VPC_ID}"
else
  nat_filter="Name=tag:${PROJECT_TAG_KEY},Values=${PROJECT_TAG_VALUE}"
fi
nat_left="$(aws ec2 describe-nat-gateways --region "$AWS_REGION_VALUE" \
  --filter "$nat_filter" Name=state,Values=pending,available,deleting \
  --query 'length(NatGateways)' --output text 2>/dev/null || echo "?")"
if [[ "$nat_left" == "?" ]]; then
  echo -e "  ${YELLOW}SKIP${NC}  NAT gateways: the query failed."
else
  check "NAT gateways deleted" "$nat_left" "A NAT gateway costs money every hour. 'deleting' may finish in a minute."
fi

eip_left="$(aws ec2 describe-addresses --region "$AWS_REGION_VALUE" \
  --filters "Name=tag:${PROJECT_TAG_KEY},Values=${PROJECT_TAG_VALUE}" \
  --query 'length(Addresses)' --output text 2>/dev/null || echo "?")"
if [[ "$eip_left" == "?" ]]; then
  echo -e "  ${YELLOW}SKIP${NC}  Elastic IPs: the query failed."
else
  check "Elastic IPs released" "$eip_left" "An unattached Elastic IP is billed."
fi

if [[ -n "$CLUSTER_NAME" ]]; then
  log_group="/aws/eks/${CLUSTER_NAME}/cluster"
  lg_left="$(aws logs describe-log-groups --region "$AWS_REGION_VALUE" \
    --log-group-name-prefix "$log_group" \
    --query "length(logGroups[?logGroupName=='${log_group}'])" --output text 2>/dev/null || echo "?")"
  if [[ "$lg_left" == "?" ]]; then
    echo -e "  ${YELLOW}SKIP${NC}  CloudWatch log group: the query failed."
  else
    check "CloudWatch log group ${log_group} is gone" "$lg_left" \
      "Delete it manually: aws logs delete-log-group --log-group-name ${log_group}"
  fi
fi

# --------------------------------------------------------------------------
# Step 7: remove this cluster from ~/.kube/config
# --------------------------------------------------------------------------
CURRENT_PHASE="removing kubeconfig entries"
step 7 "Cleaning your ~/.kube/config" "Removes only this cluster's context, cluster and user entries, so kubectl does not point at a dead cluster."
if [[ -n "$CLUSTER_NAME" ]] && command -v kubectl >/dev/null 2>&1; then
  entry="arn:aws:eks:${AWS_REGION_VALUE}:${ACCOUNT_ID}:cluster/${CLUSTER_NAME}"
  removed=false
  for name in "$entry" "$CLUSTER_NAME"; do
    if kubectl config get-contexts -o name 2>/dev/null | grep -x "$name" >/dev/null; then
      kubectl config delete-context "$name" >/dev/null 2>&1 && removed=true
    fi
    if kubectl config get-clusters 2>/dev/null | grep -x "$name" >/dev/null; then
      kubectl config delete-cluster "$name" >/dev/null 2>&1 && removed=true
    fi
    kubectl config unset "users.${name}" >/dev/null 2>&1 || true
  done
  if [[ "$removed" == "true" ]]; then
    print_success "Removed the entries for ${CLUSTER_NAME}."
  else
    echo "  No entries for ${CLUSTER_NAME} found."
  fi
else
  echo "  Nothing to clean."
fi

echo
if [[ "$FAILED" -eq 0 ]]; then
  echo -e "${GREEN}==================================================${NC}"
  echo -e "${GREEN}✅ Teardown complete. All checks passed.${NC}"
  echo -e "${GREEN}==================================================${NC}"
else
  echo -e "${RED}==================================================${NC}"
  echo -e "${RED}⚠️  Teardown finished, but some checks FAILED (see above).${NC}"
  echo -e "${RED}   Fix those items by hand so they stop costing money.${NC}"
  echo -e "${RED}==================================================${NC}"
  exit 1
fi
