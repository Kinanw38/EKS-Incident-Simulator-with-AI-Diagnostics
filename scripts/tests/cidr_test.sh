#!/usr/bin/env bash
# Tests for scripts/lib/cidr.sh. No AWS and no network needed.
# shellcheck disable=SC2034  # DETECTED_ADDRESSES is set by detect_allowed_cidr
# Run: bash scripts/tests/cidr_test.sh
set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=../lib/cidr.sh
source "$SCRIPT_DIR/../lib/cidr.sh"

failures=0

expect() {
  local description="$1" expected="$2" actual="$3"
  if [[ "$expected" == "$actual" ]]; then
    echo "PASS  $description"
  else
    echo "FAIL  $description: expected '$expected', got '$actual'"
    failures=$((failures + 1))
  fi
}

expect_valid()   { if is_ipv4 "$1"; then echo "PASS  valid: $1"; else echo "FAIL  should be valid: $1"; failures=$((failures + 1)); fi; }
expect_invalid() { if is_ipv4 "$1"; then echo "FAIL  should be invalid: $1"; failures=$((failures + 1)); else echo "PASS  invalid: $1"; fi; }

expect_valid 203.0.113.7
expect_valid 0.0.0.0
expect_valid 255.255.255.255
expect_invalid 256.1.1.1
expect_invalid 1.2.3
expect_invalid 1.2.3.4.5
expect_invalid abc
expect_invalid "2001:db8::1"
expect_invalid ""

expect "one address is a /32" "203.0.113.7/32" "$(covering_cidr 203.0.113.7)"
expect "the same address twice is a /32" "203.0.113.7/32" "$(covering_cidr 203.0.113.7 203.0.113.7)"
expect "two addresses in one /24" "203.0.113.0/25" "$(covering_cidr 203.0.113.7 203.0.113.100)"
expect "addresses across two /24 blocks" "198.18.4.0/23" "$(covering_cidr 198.18.4.23 198.18.5.3)"
expect "order does not matter" "198.18.4.0/23" "$(covering_cidr 198.18.5.3 198.18.4.23)"
expect "three addresses" "10.0.0.0/22" "$(covering_cidr 10.0.0.1 10.0.1.9 10.0.3.250)"
expect "far apart addresses give a wide range" "64.0.0.0/2" "$(covering_cidr 100.1.1.1 64.0.0.1)"
expect "prefix of a CIDR" "23" "$(cidr_prefix 198.18.4.0/23)"
expect "int round trip" "198.18.4.23" "$(int_to_ip "$(ip_to_int 198.18.4.23)")"

# --- detect_allowed_cidr, with the "what is my IP" lookups replaced by a stub ---
run_detect() {
  # $1 = value of EKS_ALLOWED_CIDR (may be empty); the rest = addresses the stub returns
  local requested="$1"; shift
  STUB_IPS=("$@")
  sample_public_ips() { printf '%s\n' "${STUB_IPS[@]}"; }
  CIDR_SOURCE="" ALLOWED_CIDR="" DETECTED_ADDRESSES=""
  EKS_ALLOWED_CIDR="$requested"
  local status=0
  detect_allowed_cidr || status=$?
  echo "$status ${CIDR_SOURCE:-none} ${ALLOWED_CIDR:-none}"
}

expect "stable address -> /32" "0 auto 203.0.113.7/32" \
  "$(run_detect "" 203.0.113.7 203.0.113.7 203.0.113.7)"
expect "rotating addresses -> covering range" "0 auto 198.18.4.0/23" \
  "$(run_detect "" 198.18.4.23 198.18.5.3 198.18.4.23)"
expect "no address found -> status 1" "1 none none" \
  "$(run_detect "")"
expect "addresses too far apart -> status 2" "2 none none" \
  "$(run_detect "" 100.1.1.1 64.0.0.1)"
expect "manual range is used as given" "0 manual 198.51.100.0/24" \
  "$(run_detect "198.51.100.0/24" 203.0.113.7)"
expect "open is explicit" "0 open 0.0.0.0/0" \
  "$(run_detect "open" 203.0.113.7)"

if (( failures > 0 )); then
  echo "$failures test(s) failed."
  exit 1
fi
echo "All CIDR tests passed."
