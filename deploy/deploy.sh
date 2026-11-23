#!/usr/bin/env bash
# Deploys the checked-out commit to ~/ekcall and restarts the services (docs/deploy.md).
# Run by the CD workflow on our self-hosted runner, from the fresh checkout:  bash deploy/deploy.sh
#
# Server-only files are never overwritten or deleted: backend/.env, frontend/.env*, the database,
# the Chroma store and the models. Dependencies are reinstalled only when their lock files change;
# the documents are re-ingested (and the answer cache pre-warmed) only when they change.
set -euo pipefail

SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
EKCALL_HOME="${EKCALL_HOME:-$HOME/ekcall}"
APP="$EKCALL_HOME/app"
VENV="$EKCALL_HOME/venv"
STAMPS="$EKCALL_HOME/stamps"
BACKEND_URL="http://localhost:8000/health"
FRONTEND_URL="http://localhost:4173/"

step() { echo "::group::$1"; }
done_step() { echo "::endgroup::"; }
fail() { echo "::error::$1"; exit 1; }

[ -f "$EKCALL_HOME/config.env" ] || fail "run deploy/install.sh on the server first"
# shellcheck disable=SC1091
. "$EKCALL_HOME/config.env"
export PATH="$NODE_BIN:$PATH"
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"  # systemctl --user from the runner
mkdir -p "$STAMPS"

OLD_SHA="$(cat "$EKCALL_HOME/DEPLOYED_SHA" 2>/dev/null || true)"
NEW_SHA="$(git -C "$SRC" rev-parse HEAD)"
echo "deploying ${NEW_SHA:0:7} (was ${OLD_SHA:0:7})"

# True when a path changed since the last deploy (or we cannot tell).
changed() {
  [ -n "$OLD_SHA" ] || return 0
  git -C "$SRC" cat-file -e "$OLD_SHA^{commit}" 2>/dev/null || return 0
  ! git -C "$SRC" diff --quiet "$OLD_SHA" "$NEW_SHA" -- "$@"
}

# True when the file's hash differs from the one stored for it, i.e. its packages must be installed.
needs_install() {
  local file="$1" stamp="$STAMPS/$2"
  [ "$(sha256sum "$file" | cut -d' ' -f1)" != "$(cat "$stamp" 2>/dev/null || true)" ]
}
mark_installed() { sha256sum "$1" | cut -d' ' -f1 > "$STAMPS/$2"; }

# ------------------------------------------------------------------ 1. code
step "Copy code to $APP"
rsync -a --delete \
  --exclude '.git/' --exclude '__pycache__/' --exclude '.pytest_cache/' --exclude '.ruff_cache/' \
  --exclude 'backend/.venv/' --exclude 'backend/.env' \
  --exclude 'backend/data/chroma/' --exclude 'backend/data/models/' --exclude 'backend/data/ekcall.db*' \
  --exclude 'frontend/node_modules/' --exclude 'frontend/dist/' --exclude 'frontend/.env*' \
  "$SRC/" "$APP/"
[ -f "$APP/backend/.env" ] || fail "missing $APP/backend/.env: copy it once (docs/deploy.md)"
done_step

# ------------------------------------------------------------------ 2. backend packages
step "Backend packages"
[ -x "$VENV/bin/python" ] || "$PYTHON" -m venv "$VENV"
if needs_install "$APP/backend/requirements.txt" requirements; then
  "$VENV/bin/pip" install -q --upgrade pip
  "$VENV/bin/pip" install -q torch==2.15.0 --index-url https://download.pytorch.org/whl/cpu
  "$VENV/bin/pip" install -q -r "$APP/backend/requirements.txt"
  mark_installed "$APP/backend/requirements.txt" requirements
else
  echo "requirements.txt unchanged"
fi
"$VENV/bin/python" -c "import normalizer" 2>/dev/null ||
  "$VENV/bin/pip" install -q git+https://github.com/csebuetnlp/normalizer
done_step

# ------------------------------------------------------------------ 3. documents
REINGEST=false
if [ ! -d "$APP/backend/data/chroma" ] || changed backend/data/raw_docs backend/data/services.yaml; then
  REINGEST=true
  step "Ingest documents (they changed)"
  (cd "$APP/backend" && "$VENV/bin/python" -m scripts.ingest)
  done_step
fi

# ------------------------------------------------------------------ 4. frontend build
step "Frontend build"
cd "$APP/frontend"
if needs_install package-lock.json npm || [ ! -d node_modules ]; then
  npm ci --no-audit --no-fund
  mark_installed package-lock.json npm
fi
npm run build
done_step

# ------------------------------------------------------------------ 5. restart and check
step "Restart services"
systemctl --user restart ekcall-backend.service ekcall-frontend.service
ok=false
for _ in $(seq 1 60); do
  if curl -fsS -o /dev/null "$BACKEND_URL" && curl -fsS -o /dev/null "$FRONTEND_URL"; then
    ok=true
    break
  fi
  sleep 2
done
if ! $ok; then
  journalctl --user -u ekcall-backend.service -n 40 --no-pager || true
  fail "the services did not come up within 2 minutes"
fi
curl -fsS "$BACKEND_URL"
echo
done_step

# ------------------------------------------------------------------ 6. answer cache
if $REINGEST; then
  step "Pre-warm the answer cache (ingest cleared it)"
  (cd "$APP/backend" && "$VENV/bin/python" -m scripts.prewarm --voice) ||
    echo "::warning::prewarm failed (Gemini busy?); run it again by hand"
  done_step
fi

echo "$NEW_SHA" > "$EKCALL_HOME/DEPLOYED_SHA"
echo "deployed ${NEW_SHA:0:7}"
