#!/usr/bin/env bash
# Small helpers for IPv4 addresses and CIDR ranges.
# Sourced by setup.sh and by scripts/tests/cidr_test.sh (no AWS needed).
# shellcheck disable=SC2034  # the variables below are read by the scripts that source this file

# Succeeds only for a valid dotted IPv4 address such as 203.0.113.7.
is_ipv4() {
  local ip="$1" octet
  [[ "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || return 1
  local IFS=.
  for octet in $ip; do
    (( 10#$octet <= 255 )) || return 1
  done
}

ip_to_int() {
  local IFS=. a b c d
  read -r a b c d <<< "$1"
  echo $(( (10#$a << 24) | (10#$b << 16) | (10#$c << 8) | 10#$d ))
}

int_to_ip() {
  local n="$1"
  echo "$(( (n >> 24) & 255 )).$(( (n >> 16) & 255 )).$(( (n >> 8) & 255 )).$(( n & 255 ))"
}

# Prints the smallest CIDR range that contains every given IPv4 address.
#   covering_cidr 203.0.113.7                    -> 203.0.113.7/32
#   covering_cidr 198.18.4.23 198.18.5.3     -> 198.18.4.0/23
covering_cidr() {
  local ip n min max
  for ip in "$@"; do
    n="$(ip_to_int "$ip")"
    if [[ -z "${min:-}" ]] || (( n < min )); then min="$n"; fi
    if [[ -z "${max:-}" ]] || (( n > max )); then max="$n"; fi
  done

  # The addresses share the leading bits where min and max agree.
  local diff=$(( min ^ max )) bits=0
  while (( diff > 0 )); do
    diff=$(( diff >> 1 ))
    bits=$(( bits + 1 ))
  done

  local prefix=$(( 32 - bits ))
  local mask=$(( (0xFFFFFFFF << (32 - prefix)) & 0xFFFFFFFF ))
  echo "$(int_to_ip $(( min & mask )))/${prefix}"
}

# Prints the prefix length of a CIDR ("198.18.4.0/23" -> 23).
cidr_prefix() {
  echo "${1##*/}"
}

# Which public addresses may talk to the EKS API endpoint?
#
# Default: ask a few "what is my IP" services a couple of times each, and allow
# the smallest range that contains every address seen. Many home and mobile
# connections leave the internet from more than one address, so a single /32
# would lock you out of your own cluster. A very wide range (broader than
# /16) is refused: set EKS_ALLOWED_CIDR yourself in that case.
#
# EKS_ALLOWED_CIDR can be:
#   a CIDR such as 203.0.113.7/32   use exactly that
#   open                            0.0.0.0/0, the API is reachable from anywhere
#                                   (AWS credentials are still required, but it
#                                   is not recommended)
# The result is stored in ALLOWED_CIDR, and how it was chosen in CIDR_SOURCE.
CIDR_SOURCE=""
ALLOWED_CIDR=""

sample_public_ips() {
  local url ip
  for url in https://checkip.amazonaws.com https://api.ipify.org https://ifconfig.me/ip; do
    for _ in 1 2; do
      ip="$(curl --ipv4 --silent --fail --max-time 8 "$url" 2>/dev/null | tr -d '[:space:]')" || ip=""
      if is_ipv4 "$ip"; then
        echo "$ip"
      fi
    done
  done
}

# Sets ALLOWED_CIDR, CIDR_SOURCE and DETECTED_ADDRESSES (so it must NOT be
# called inside $(...), which would hide the variables).
# Returns 0 on success, 1 if no address could be detected, 2 if the detected
# addresses need a range broader than /16.
detect_allowed_cidr() {
  local requested="${EKS_ALLOWED_CIDR:-}"

  if [[ "$requested" == "open" ]]; then
    CIDR_SOURCE="open"
    ALLOWED_CIDR="0.0.0.0/0"
    return 0
  fi

  if [[ -n "$requested" ]]; then
    CIDR_SOURCE="manual"
    ALLOWED_CIDR="$requested"
    return 0
  fi

  local unique
  unique="$(sample_public_ips | sort -u | tr '\n' ' ')"
  unique="${unique% }"

  if [[ -z "$unique" ]]; then
    return 1
  fi

  DETECTED_ADDRESSES="$unique"

  local addresses
  read -ra addresses <<< "$unique"

  local cidr
  cidr="$(covering_cidr "${addresses[@]}")"

  if (( $(cidr_prefix "$cidr") < 16 )); then
    return 2
  fi

  CIDR_SOURCE="auto"
  ALLOWED_CIDR="$cidr"
}


DETECTED_ADDRESSES=""
