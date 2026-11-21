#!/usr/bin/env bash
# SRK Placement AI - laptop par chalane ke liye (Mac / Linux, Docker Desktop ya Docker Engine)
#   bash start.sh
set -euo pipefail
cd "$(dirname "$0")"
command -v docker >/dev/null || { echo "Docker nahi mila: https://www.docker.com/products/docker-desktop/"; exit 1; }
docker info >/dev/null 2>&1 || { echo "Docker chalu nahi hai. Docker Desktop kholiye aur dobara chalaiye."; exit 1; }
if [[ ! -f .env ]]; then
  sed -e "s/^JWT_SECRET=.*/JWT_SECRET=$(openssl rand -hex 32)/" \
      -e "s/^POSTGRES_PASSWORD=.*/POSTGRES_PASSWORD=$(openssl rand -hex 16)/" \
      -e "s/^APP_PORT=.*/APP_PORT=8080/" .env.example > .env
  echo ".env bana di (demo data ke saath)."
fi
echo "App ban raha hai... pehli baar 5-10 minute lagte hain."
docker compose up -d --build
for i in $(seq 1 60); do curl -fs http://localhost:8080/api/health >/dev/null && break; sleep 3; done
echo
echo "Chal gaya!  http://localhost:8080"
echo "Demo login (password Srk@2026): tpo@srk.demo, coord.esm@srk.demo, student001@srk.demo"
echo "Band karne ke liye:  docker compose stop"
(command -v open >/dev/null && open http://localhost:8080) || (command -v xdg-open >/dev/null && xdg-open http://localhost:8080) || true
