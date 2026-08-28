#!/usr/bin/env bash
# Port-forwards np-data01's PostgreSQL (192.168.10.21:5432) to
# localhost:5433, so you can psql/connect to the np beta database from your
# workstation without being on the 192.168.10.0/24 subnet directly.
#
# Prereqs:
#   - GDCC-NP PPTP tunnel up first: rasdial GDCC-NP
#     (ping 192.168.10.10 should answer once it's connected)
#   - the np-data01 webmaster password (credentials/np_hosts.yml if you have
#     the ops repo, otherwise ask whoever owns it)
#   - sshpass installed (apt-get install -y sshpass on WSL/Debian/Ubuntu)
#
# np has no bastion — every service is forwarded through its own host
# directly, and any ~/.ssh/config ProxyJump you have for the PRODUCTION
# 192.168.10.* range (lb15-bastion) does not route here and must be bypassed
# with -F /dev/null (dev-np-quickstart.md §3.2 / §3.3).
#
# Usage:
#   ./scripts/np-db-tunnel.sh
#   NP_DATA01_PASS=xxx ./scripts/np-db-tunnel.sh     # non-interactive
#
# Then, in another terminal:
#   psql -h 127.0.0.1 -p 5433 -U admin -d case_service
# (the "admin" role's password is in credentials/np_112_captured_env/ — not
# credentials/np_postgres_app_pass, that's the other role and won't work)

set -euo pipefail

NP_DATA01_HOST="192.168.10.21"
NP_DATA01_USER="webmaster"
LOCAL_PORT="5433"

if ! command -v sshpass >/dev/null 2>&1; then
    echo "sshpass not found — install it first: sudo apt-get install -y sshpass" >&2
    exit 1
fi

if [ -z "${NP_DATA01_PASS:-}" ]; then
    read -rsp "np-data01 (${NP_DATA01_USER}) password: " NP_DATA01_PASS
    echo
fi
export SSHPASS="${NP_DATA01_PASS}"

echo "Forwarding localhost:${LOCAL_PORT} -> ${NP_DATA01_HOST}:5432 (Ctrl+C to stop)"

sshpass -e ssh -F /dev/null \
    -o PubkeyAuthentication=no \
    -o PreferredAuthentications=password \
    -o StrictHostKeyChecking=accept-new \
    -o ServerAliveInterval=30 -o ServerAliveCountMax=2 \
    -N -L "${LOCAL_PORT}:127.0.0.1:5432" \
    "${NP_DATA01_USER}@${NP_DATA01_HOST}"
