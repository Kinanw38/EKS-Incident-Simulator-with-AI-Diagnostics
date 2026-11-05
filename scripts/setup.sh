#!/usr/bin/env bash

set -Eeuo pipefail

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
TERRAFORM_DIR="$PROJECT_ROOT/terraform"
BACKEND_DIR="$PROJECT_ROOT/backend"
FRONTEND_DIR="$PROJECT_ROOT/frontend"
LOG_DIR="$PROJECT_ROOT/.logs"

BACKEND_LOG="$LOG_DIR/backend.log"
FRONTEND_LOG="$LOG_DIR/frontend.log"
BACKEND_PID_FILE="$LOG_DIR/backend.pid"
FRONTEND_PID_FILE="$LOG_DIR/frontend.pid"
REQUIREMENTS_STAMP="$BACKEND_DIR/.venv/.requirements-installed"

BACKEND_PORT="${BACKEND_PORT:-8000}"
FRONTEND_PORT="${FRONTEND_PORT:-3000}"

ASSUME_YES=false
for arg in "$@"; do
  case "$arg" in
    -y|--yes) ASSUME_YES=true ;;
    -h|--help)
      echo "Usage: ./scripts/setup.sh [--yes]"
      echo "  --yes  skip the confirmation questions"
      exit 0
      ;;
    *)
      echo "Unknown option: $arg" >&2
      exit 1
      ;;
  esac
done

# Updated before every phase, so the error message can say what failed.
CURRENT_PHASE="starting"

mkdir -p "$LOG_DIR"

print_error() { echo -e "${RED}❌ $1${NC}" >&2; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }

TOTAL_STEPS=9

# Prints a clear header for each phase: what is happening and why.
step() {
  local number="$1"
  local title="$2"
  local why="$3"
  echo
  echo -e "${BLUE}━━━ Step ${number}/${TOTAL_STEPS}: ${title} ━━━${NC}"
  echo "    ${why}"
}

cleanup_on_error() {
  print_error "Setup failed during phase: ${CURRENT_PHASE}."
  echo
  if [[ "$CURRENT_PHASE" == "terraform apply" || "$CURRENT_PHASE" == "terraform import" ]]; then
    print_warning "Terraform may have created some AWS resources before failing."
    echo "To avoid paying for leftovers, run: ./scripts/destroy.sh"
    echo
  fi
  echo "Check the following logs if a service failed:"
  echo "  Backend:  $BACKEND_LOG"
  echo "  Frontend: $FRONTEND_LOG"
  exit 1
}

trap cleanup_on_error ERR

command_exists() { command -v "$1" >/dev/null 2>&1; }

require_command() {
  if ! command_exists "$1"; then
    print_error "Required command '$1' was not found in PATH."
    echo "Install '$1' and run this script again."
    exit 1
  fi
}

is_process_running_from_pid_file() {
  local pid_file="$1"

  if [[ ! -f "$pid_file" ]]; then
    return 1
  fi

  local pid
  pid="$(cat "$pid_file")"

  [[ "$pid" =~ ^[0-9]+$ ]] && kill -0 "$pid" >/dev/null 2>&1
}

stop_stale_process() {
  local name="$1"
  local pid_file="$2"

  if [[ -f "$pid_file" ]] && ! is_process_running_from_pid_file "$pid_file"; then
    echo "Removing stale $name PID file."
    rm -f "$pid_file"
  fi
}

check_prerequisites() {
  step 1 "Checking your tools" "Terraform builds the cluster, aws/kubectl talk to it, python/npm run the app."
  require_command terraform
  require_command aws
  require_command kubectl
  require_command python3
  require_command npm
  require_command curl
  check_terraform_version
  print_success "All required tools are available."
}

# Terraform >= 1.9 is needed (variable validation that references other variables).
check_terraform_version() {
  local version major minor
  version="$(terraform version | head -n 1 | sed -E 's/^Terraform v([0-9]+\.[0-9]+).*/\1/')"
  major="${version%%.*}"
  minor="${version#*.}"
  if (( major < 1 || (major == 1 && minor < 9) )); then
    print_error "Terraform 1.9 or newer is required (found $version)."
    exit 1
  fi
}

ask_yes_no() {
  local question="$1"
  if [[ "$ASSUME_YES" == "true" ]]; then
    return 0
  fi
  local answer
  read -r -p "$question [y/N] " answer
  [[ "$answer" =~ ^[Yy]$ ]]
}

confirm_account_and_cost() {
  CURRENT_PHASE="AWS identity check"
  step 2 "Confirming your AWS account" "So you never create resources in the wrong account by accident."
  local account region
  account="$(aws sts get-caller-identity --query Account --output text)"
  region="${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || true)}}"
  region="${region:-us-east-1 (Terraform default)}"

  echo "  AWS account: $account"
  echo "  Region:      $region"
  echo
  echo "💰 Approximate cost while the cluster is running: about 0.23-0.25 USD per hour"
  echo "   (roughly 5-6 USD per day). Main parts:"
  echo "  - EKS control plane   ~ 0.10 USD/h"
  echo "  - NAT gateway         ~ 0.045 USD/h + data transfer"
  echo "  - 2 x t3.medium nodes ~ 0.08 USD/h"
  echo "  - public IPv4 addresses, logs, and similar small items"
  print_warning "Leaving the cluster running burns money (or credits) fast."
  echo "Run ./scripts/destroy.sh as soon as you are done. This is an estimate, not a bill."
  echo

  if ! ask_yes_no "Create these resources in account $account?"; then
    echo "Cancelled. Nothing was created."
    exit 0
  fi
}

# Fail early with a clear message if a port is already used by something else.
port_in_use() {
  (exec 3<>"/dev/tcp/127.0.0.1/$1") 2>/dev/null
}

# The EKS API endpoint is public, so we restrict it to the caller's own IP.
# Override with EKS_ALLOWED_CIDR (for example "203.0.113.7/32").
detect_allowed_cidr() {
  if [[ -n "${EKS_ALLOWED_CIDR:-}" ]]; then
    echo "$EKS_ALLOWED_CIDR"
    return 0
  fi

  local ip
  ip="$(curl --silent --fail --max-time 10 https://checkip.amazonaws.com | tr -d '[:space:]')" || true

  if [[ ! "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]]; then
    return 1
  fi

  echo "${ip}/32"
}

# Older runs let EKS create the CloudWatch log group by itself, so it can
# survive "terraform destroy". If it exists in AWS but Terraform does not
# know it, "terraform apply" would fail with "already exists". Importing
# adopts the existing group into the state instead.
import_existing_log_group() {
  local allowed_cidr="$1"
  local cluster_name log_group address
  cluster_name="$(echo 'var.cluster_name' | terraform console | tr -d '"[:space:]')"
  log_group="/aws/eks/${cluster_name}/cluster"
  address="aws_cloudwatch_log_group.cluster"

  if terraform state list 2>/dev/null | grep -qx "$address"; then
    return 0
  fi

  local found
  found="$(aws logs describe-log-groups \
    --log-group-name-prefix "$log_group" \
    --query "logGroups[?logGroupName=='${log_group}'].logGroupName" \
    --output text)"

  if [[ "$found" == "$log_group" ]]; then
    print_warning "Log group $log_group already exists outside Terraform; importing it."
    terraform import -var "public_access_cidrs=[\"${allowed_cidr}\"]" "$address" "$log_group"
  fi
}

provision_infrastructure() {
  step 3 "Building the AWS infrastructure" "Terraform creates the network, the EKS cluster and the worker nodes. This usually takes 10-15 minutes, please wait."

  local allowed_cidr
  if ! allowed_cidr="$(detect_allowed_cidr)"; then
    print_error "Could not detect your public IP address."
    echo "The EKS API endpoint must not be left open to the whole internet."
    echo "Set it yourself and run again, for example:"
    echo "  EKS_ALLOWED_CIDR=203.0.113.7/32 ./scripts/setup.sh"
    exit 1
  fi
  echo "EKS API endpoint will be reachable only from: $allowed_cidr"
  echo "(If your IP changes later, run this script again to update it.)"

  cd "$TERRAFORM_DIR"

  CURRENT_PHASE="terraform init"
  terraform init

  CURRENT_PHASE="terraform import"
  import_existing_log_group "$allowed_cidr"

  CURRENT_PHASE="terraform apply"
  terraform apply -auto-approve -var "public_access_cidrs=[\"${allowed_cidr}\"]"

  CLUSTER_NAME="$(terraform output -raw cluster_name)"
  AWS_REGION="$(terraform output -raw cluster_region)"

  if [[ -z "$CLUSTER_NAME" || -z "$AWS_REGION" ]]; then
    print_error "Terraform did not return cluster_name or cluster_region."
    exit 1
  fi

  export CLUSTER_NAME
  export AWS_REGION

  echo
  echo "Cluster: $CLUSTER_NAME"
  echo "Region:  $AWS_REGION"

  echo
  CURRENT_PHASE="kubeconfig update"
  step 4 "Connecting kubectl to the new cluster" "Adds the cluster to ~/.kube/config so kubectl knows where to send commands."
  aws eks update-kubeconfig --region "$AWS_REGION" --name "$CLUSTER_NAME"
}

wait_for_kubernetes() {
  CURRENT_PHASE="waiting for Kubernetes nodes"
  step 5 "Waiting for the worker nodes" "The cluster is only usable when every node reports Ready (waits up to 5 minutes)."
  kubectl wait --for=condition=Ready nodes --all --timeout=300s
  print_success "Kubernetes nodes are Ready."
}

# metrics-server gives the dashboard real CPU/memory usage in Live Mode.
# It is one small pod (requests 100m CPU / 200Mi) on the existing nodes and
# creates no AWS resources. If it fails, the dashboard still works and shows
# "reserved" numbers instead, so this step never stops the setup.
install_metrics_server() {
  CURRENT_PHASE="installing metrics-server"
  step 6 "Installing metrics-server" "Lets the dashboard show real CPU and memory usage. One small pod, no extra AWS cost."

  if kubectl apply -f "$PROJECT_ROOT/k8s/metrics-server/components.yaml" \
    && kubectl -n kube-system rollout status deployment/metrics-server --timeout=180s; then
    print_success "metrics-server is running (usage numbers appear about a minute later)."
  else
    print_warning "metrics-server did not become ready. The dashboard will show reserved CPU/memory only."
  fi
}

prepare_backend() {
  CURRENT_PHASE="backend preparation"
  step 7 "Preparing the Python backend" "Creates a private virtual environment and installs the pinned dependencies."

  if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
    python3 -m venv "$BACKEND_DIR/.venv"
    print_success "Created backend virtual environment."
  else
    echo "Backend virtual environment already exists."
  fi

  # shellcheck disable=SC1091
  source "$BACKEND_DIR/.venv/bin/activate"

  local requirements_hash
  if command_exists sha256sum; then
    requirements_hash="$(sha256sum "$BACKEND_DIR/requirements.txt" | awk '{print $1}')"
  else
    requirements_hash="$(shasum -a 256 "$BACKEND_DIR/requirements.txt" | awk '{print $1}')"
  fi

  local installed_hash=""
  if [[ -f "$REQUIREMENTS_STAMP" ]]; then
    installed_hash="$(cat "$REQUIREMENTS_STAMP")"
  fi

  if [[ "$requirements_hash" != "$installed_hash" ]]; then
    echo "Installing or updating backend dependencies..."
    python -m pip install --upgrade pip
    python -m pip install -r "$BACKEND_DIR/requirements.txt"
    echo "$requirements_hash" > "$REQUIREMENTS_STAMP"
    print_success "Backend dependencies are ready."
  else
    echo "Backend dependencies are already up to date."
  fi

  deactivate
}

prepare_frontend() {
  CURRENT_PHASE="frontend preparation"
  step 8 "Preparing the frontend" "Installs the exact npm packages from package-lock.json."

  if [[ ! -d "$FRONTEND_DIR/node_modules" ]]; then
    (
      cd "$FRONTEND_DIR"
      npm ci
    )
    print_success "Frontend dependencies installed."
  else
    echo "Frontend node_modules already exists; skipping npm install."
  fi
}

# Each service runs in its own process group (setsid), and we record the
# group id (PGID) in the pid file. "npm run dev" starts child processes;
# killing only the npm process can leave an orphan holding the port, but
# killing the whole group stops the entire tree.
stop_existing_service() {
  local name="$1"
  local pid_file="$2"

  if is_process_running_from_pid_file "$pid_file"; then
    local pgid
    pgid="$(cat "$pid_file")"

    echo "Stopping existing $name process group ($pgid)..."
    kill -- "-$pgid" >/dev/null 2>&1 || kill "$pgid" >/dev/null 2>&1 || true

    for _ in {1..20}; do
      if ! kill -0 "$pgid" >/dev/null 2>&1; then
        break
      fi
      sleep 0.5
    done

    if kill -0 "$pgid" >/dev/null 2>&1; then
      print_warning "$name did not stop gracefully; terminating it."
      kill -9 -- "-$pgid" >/dev/null 2>&1 || kill -9 "$pgid" >/dev/null 2>&1 || true
    fi
  fi

  rm -f "$pid_file"
}

# Run a command detached in its own process group and write the PGID to a file.
start_detached() {
  local pid_file="$1"
  local log_file="$2"
  shift 2

  if command_exists setsid; then
    setsid nohup "$@" > "$log_file" 2>&1 &
  else
    nohup "$@" > "$log_file" 2>&1 &
  fi
  echo $! > "$pid_file"
}

check_port_free() {
  local name="$1"
  local port="$2"
  if port_in_use "$port"; then
    print_error "Port $port ($name) is already in use by another program."
    echo "Stop that program, or choose another port, for example:"
    echo "  BACKEND_PORT=8001 FRONTEND_PORT=3001 ./scripts/setup.sh"
    exit 1
  fi
}

start_backend() {
  CURRENT_PHASE="starting backend"
  step 9 "Starting the app" "Backend (API) and frontend (dashboard) run on this machine only, at 127.0.0.1."
  echo "Starting the live FastAPI backend..."

  stop_existing_service "backend" "$BACKEND_PID_FILE"
  check_port_free "backend" "$BACKEND_PORT"

  # Bound to 127.0.0.1 on purpose: this backend has no authentication and
  # can run kubectl against your cluster, so only this machine may reach it.
  (
    cd "$BACKEND_DIR"
    unset DEMO_MODE
    start_detached "$BACKEND_PID_FILE" "$BACKEND_LOG" \
      "$BACKEND_DIR/.venv/bin/uvicorn" app.main:app \
      --host 127.0.0.1 \
      --port "$BACKEND_PORT"
  )

  sleep 3

  if ! is_process_running_from_pid_file "$BACKEND_PID_FILE"; then
    print_error "Backend failed to start."
    tail -n 80 "$BACKEND_LOG" || true
    exit 1
  fi

  if ! curl --silent --fail "http://127.0.0.1:${BACKEND_PORT}/api/health" >/dev/null 2>&1; then
    print_warning "Backend process is running, but the health endpoint is not ready yet."
    echo "Check: $BACKEND_LOG"
  else
    print_success "Backend is running."
  fi
}

start_frontend() {
  CURRENT_PHASE="starting frontend"
  echo "Starting the Vite frontend..."

  stop_existing_service "frontend" "$FRONTEND_PID_FILE"
  check_port_free "frontend" "$FRONTEND_PORT"

  (
    cd "$FRONTEND_DIR"
    start_detached "$FRONTEND_PID_FILE" "$FRONTEND_LOG" \
      npm run dev -- \
      --host 127.0.0.1 \
      --port "$FRONTEND_PORT"
  )

  sleep 3

  if ! is_process_running_from_pid_file "$FRONTEND_PID_FILE"; then
    print_error "Frontend failed to start."
    tail -n 80 "$FRONTEND_LOG" || true
    exit 1
  fi

  print_success "Frontend process is running."
}

print_summary() {
  local frontend_url
  frontend_url="$(
    grep -Eo 'http://(localhost|127\.0\.0\.1):[0-9]+' "$FRONTEND_LOG" \
      | head -n 1 \
      || true
  )"

  if [[ -z "$frontend_url" ]]; then
    frontend_url="http://localhost:${FRONTEND_PORT}"
  fi

  echo
  echo -e "${GREEN}==================================================${NC}"
  echo -e "${GREEN}✅ AI Incident Simulator is ready${NC}"
  echo -e "${GREEN}==================================================${NC}"
  echo
  echo "Mode:     LIVE (real cluster, real kubectl commands)"
  echo "Cluster:  ${CLUSTER_NAME:-unknown}"
  echo "Region:   ${AWS_REGION:-unknown}"
  echo
  echo "Frontend: $frontend_url"
  echo "Backend:  http://localhost:${BACKEND_PORT}"
  echo "API docs: http://localhost:${BACKEND_PORT}/docs"
  echo
  echo "Logs:"
  echo "  Backend:  $BACKEND_LOG"
  echo "  Frontend: $FRONTEND_LOG"
  echo
  echo "Open the Frontend address in your browser."
  echo "REMINDER: the cluster costs money while it runs."
  echo "To stop local services and destroy ALL AWS resources:"
  echo "  ./scripts/destroy.sh"
  echo
}

check_prerequisites
confirm_account_and_cost
provision_infrastructure
wait_for_kubernetes
install_metrics_server
prepare_backend
prepare_frontend
start_backend
start_frontend
print_summary