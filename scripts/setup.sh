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

mkdir -p "$LOG_DIR"

print_error() { echo -e "${RED}❌ $1${NC}" >&2; }
print_warning() { echo -e "${YELLOW}⚠️  $1${NC}"; }
print_success() { echo -e "${GREEN}✅ $1${NC}"; }

cleanup_on_error() {
  print_error "Setup failed."
  echo
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
  echo
  echo "🔍 Checking required tools..."
  require_command terraform
  require_command aws
  require_command kubectl
  require_command python3
  require_command npm
  print_success "All required tools are available."
}

provision_infrastructure() {
  echo
  echo -e "${BLUE}📦 Provisioning AWS infrastructure with Terraform...${NC}"
  cd "$TERRAFORM_DIR"

  terraform init
  terraform apply -auto-approve

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
  echo "🔗 Updating local kubeconfig..."
  aws eks update-kubeconfig --region "$AWS_REGION" --name "$CLUSTER_NAME"
}

wait_for_kubernetes() {
  echo
  echo "🩺 Waiting for the Kubernetes API..."
  local max_attempts=30
  local attempt=1

  while ! kubectl get nodes >/dev/null 2>&1; do
    if (( attempt >= max_attempts )); then
      print_error "Kubernetes API did not become ready in time."
      echo "Run this manually to investigate:"
      echo "  kubectl get nodes"
      exit 1
    fi

    echo "Waiting for Kubernetes API... attempt $attempt/$max_attempts"
    sleep 10
    attempt=$((attempt + 1))
  done

  print_success "Kubernetes API is reachable."
}

prepare_backend() {
  echo
  echo "🐍 Preparing Python backend environment..."

  if [[ ! -d "$BACKEND_DIR/.venv" ]]; then
    python3 -m venv "$BACKEND_DIR/.venv"
    print_success "Created backend virtual environment."
  else
    echo "Backend virtual environment already exists."
  fi

  # shellcheck disable=SC1091
  source "$BACKEND_DIR/.venv/bin/activate"

  local requirements_hash
  requirements_hash="$(sha256sum "$BACKEND_DIR/requirements.txt" | awk '{print $1}')"

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
  echo
  echo "📦 Preparing frontend dependencies..."

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

stop_existing_service() {
  local name="$1"
  local pid_file="$2"

  if is_process_running_from_pid_file "$pid_file"; then
    local pid
    pid="$(cat "$pid_file")"

    echo "Stopping existing $name process ($pid)..."
    kill "$pid" >/dev/null 2>&1 || true

    for _ in {1..20}; do
      if ! kill -0 "$pid" >/dev/null 2>&1; then
        break
      fi
      sleep 0.5
    done

    if kill -0 "$pid" >/dev/null 2>&1; then
      print_warning "$name did not stop gracefully; terminating it."
      kill -9 "$pid" >/dev/null 2>&1 || true
    fi
  fi

  rm -f "$pid_file"
}

start_backend() {
  echo
  echo "🚀 Starting live FastAPI backend..."

  stop_existing_service "backend" "$BACKEND_PID_FILE"

  (
    cd "$BACKEND_DIR"

    unset DEMO_MODE

    # shellcheck disable=SC1091
    source ".venv/bin/activate"

    nohup uvicorn app.main:app \
      --host 0.0.0.0 \
      --port "$BACKEND_PORT" \
      > "$BACKEND_LOG" 2>&1 &

    echo $! > "$BACKEND_PID_FILE"
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
  echo
  echo "🚀 Starting Vite frontend..."

  stop_existing_service "frontend" "$FRONTEND_PID_FILE"

  (
    cd "$FRONTEND_DIR"

    nohup npm run dev -- \
      --host 0.0.0.0 \
      --port "$FRONTEND_PORT" \
      > "$FRONTEND_LOG" 2>&1 &

    echo $! > "$FRONTEND_PID_FILE"
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
    grep -Eo 'http://(localhost|127\\.0\\.0\\.1):[0-9]+' "$FRONTEND_LOG" \
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
  echo "Mode:     LIVE"
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
  echo "To stop local services and destroy AWS resources:"
  echo "  ./scripts/destroy.sh"
  echo
}

check_prerequisites
provision_infrastructure
wait_for_kubernetes
prepare_backend
prepare_frontend
start_backend
start_frontend
print_summary