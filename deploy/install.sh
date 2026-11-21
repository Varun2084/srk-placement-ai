#!/usr/bin/env bash
# SRK Placement AI — one-command setup for a college PC/server (Ubuntu 22.04 / 24.04).
#
#   cd srk-placement-ai
#   sudo bash deploy/install.sh            # demo data (synthetic students)
#   sudo bash deploy/install.sh --real     # empty database, for real students
#   sudo bash deploy/install.sh --tunnel <CLOUDFLARE_TUNNEL_TOKEN>   # also publish over HTTPS
#
# Safe to run again: it keeps your existing .env, database and uploads.
set -euo pipefail

SEED_DEMO=1
TUNNEL_TOKEN=""
while [[ $# -gt 0 ]]; do
  case "$1" in
    --real) SEED_DEMO=0; shift ;;
    --tunnel) TUNNEL_TOKEN="${2:-}"; shift 2 ;;
    *) echo "Unknown option: $1"; exit 1 ;;
  esac
done

if [[ $EUID -ne 0 ]]; then echo "Run with sudo: sudo bash deploy/install.sh"; exit 1; fi
cd "$(dirname "$0")/.."
APP_DIR="$(pwd)"
say() { printf "\n\033[1;32m==> %s\033[0m\n" "$*"; }

say "1/5 Installing Docker (skipped if already installed)"
if ! command -v docker >/dev/null 2>&1; then
  apt-get update -y
  apt-get install -y ca-certificates curl openssl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu $(. /etc/os-release && echo "$VERSION_CODENAME") stable" \
    > /etc/apt/sources.list.d/docker.list
  apt-get update -y
  apt-get install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
fi
systemctl enable --now docker

say "2/5 Creating .env with random secrets (kept if it already exists)"
if [[ ! -f .env ]]; then
  cp .env.example .env
  sed -i "s/^JWT_SECRET=.*/JWT_SECRET=$(openssl rand -hex 32)/" .env
  sed -i "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" .env
  sed -i "s/^SEED_DEMO=.*/SEED_DEMO=${SEED_DEMO}/" .env
  if [[ "$SEED_DEMO" == "0" ]]; then
    ADMIN_PW="$(openssl rand -base64 12 | tr -d '/+=')"
    sed -i "s/^ADMIN_PASSWORD=.*/ADMIN_PASSWORD=${ADMIN_PW}/" .env
  fi
  chmod 600 .env
else
  echo ".env already exists — leaving it unchanged."
fi
if [[ -n "$TUNNEL_TOKEN" ]]; then
  grep -q '^CLOUDFLARE_TUNNEL_TOKEN=' .env && sed -i "s/^CLOUDFLARE_TUNNEL_TOKEN=.*/CLOUDFLARE_TUNNEL_TOKEN=${TUNNEL_TOKEN}/" .env \
    || echo "CLOUDFLARE_TUNNEL_TOKEN=${TUNNEL_TOKEN}" >> .env
fi

say "3/5 Building and starting the app (first time takes 5-10 minutes)"
PROFILE_ARGS=()
grep -q '^CLOUDFLARE_TUNNEL_TOKEN=.\+' .env && PROFILE_ARGS=(--profile tunnel)
docker compose "${PROFILE_ARGS[@]}" up -d --build

say "4/5 Waiting for the app to answer"
PORT=$(grep -E '^APP_PORT=' .env | cut -d= -f2); PORT=${PORT:-80}
for i in $(seq 1 60); do
  if curl -fs "http://localhost:${PORT}/api/health" >/dev/null; then echo "App is up."; break; fi
  sleep 3
  [[ $i -eq 60 ]] && { echo "App did not start. See: docker compose logs app"; exit 1; }
done

say "5/5 Daily database backup at 02:30 (kept 30 days in ${APP_DIR}/backups)"
mkdir -p backups
cat > /etc/cron.d/srk-placement-backup <<EOF
30 2 * * * root cd ${APP_DIR} && bash deploy/backup.sh >> ${APP_DIR}/backups/backup.log 2>&1
EOF

IP=$(hostname -I | awk '{print $1}')
URL="http://${IP}"; [[ "$PORT" != "80" ]] && URL="${URL}:${PORT}"
echo
echo "------------------------------------------------------------------"
echo " SRK Placement AI is running."
echo " Open on any computer/phone on the college network:  ${URL}"
[[ ${#PROFILE_ARGS[@]} -gt 0 ]] && echo " Public HTTPS link: the hostname you set in your Cloudflare Tunnel."
if [[ "$(grep -E '^SEED_DEMO=' .env | cut -d= -f2)" == "1" ]]; then
  echo " Demo logins (password Srk@2026): tpo@srk.demo, coord.esm@srk.demo, student001@srk.demo"
  echo " Before real students use it, re-run with --real on a fresh install (see docs)."
else
  echo " Admin login: $(grep -E '^ADMIN_EMAIL=' .env | cut -d= -f2)  password: $(grep -E '^ADMIN_PASSWORD=' .env | cut -d= -f2)"
  echo " Change it after first login (sidebar > Change password)."
fi
echo " It restarts by itself after a power cut or reboot."
echo "------------------------------------------------------------------"
