#!/usr/bin/env bash
# Deploys the latest main on the server: updates the project folder, rebuilds the backend image and
# restarts it. Run by the CD workflow on our self-hosted runner.
#
# Uncommitted changes in the folder are discarded. Git-ignored files (backend/.env, backend/data/...)
# are kept.
set -euo pipefail

cd ~/Desktop/Comilla-University-Hackathon

# 1. Update to main, discarding local changes.
git fetch origin main
git checkout -f main
git reset --hard origin/main
git clean -fd

# 2. Rebuild the backend image; `up -d` replaces the backend container when its image changed.
#    --wait returns only when every container is healthy, and fails otherwise.
cd backend
docker compose build backend
docker compose up -d --wait

# 3. Health of the backend container.
docker inspect --format '{{.State.Health.Status}}' ekcall-backend-1
curl -fsS http://localhost:8000/health
echo
