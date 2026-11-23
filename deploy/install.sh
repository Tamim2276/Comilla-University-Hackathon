#!/usr/bin/env bash
# One-time setup of the server that the CD workflow deploys to (docs/deploy.md).
# Run it yourself on the server, from the repo root:  bash deploy/install.sh
#
# Creates ~/ekcall (deployed code, venv, server-only files) and two systemd user services:
#   ekcall-backend   uvicorn on port 8000 (one worker: voice jobs live in memory)
#   ekcall-frontend  the built app (vite preview) on port 4173
set -euo pipefail

EKCALL_HOME="${EKCALL_HOME:-$HOME/ekcall}"
UNIT_DIR="$HOME/.config/systemd/user"

find_python() {
  for candidate in "${EKCALL_PYTHON:-}" "$(command -v python3.11 || true)" \
    "$HOME"/.local/share/uv/python/cpython-3.11*/bin/python3.11; do
    if [ -n "$candidate" ] && [ -x "$candidate" ] && "$candidate" -c 'import sys; assert sys.version_info[:2] == (3, 11)' 2>/dev/null; then
      echo "$candidate"
      return
    fi
  done
  echo "Python 3.11 not found. Set EKCALL_PYTHON=/path/to/python3.11 and run again." >&2
  exit 1
}

if ! command -v npm >/dev/null && [ -s "$HOME/.nvm/nvm.sh" ]; then
  # shellcheck disable=SC1091
  . "$HOME/.nvm/nvm.sh"
fi
NODE_BIN="$(dirname "$(command -v node)")" || { echo "Node.js not found" >&2; exit 1; }
PYTHON="$(find_python)"

mkdir -p "$EKCALL_HOME/app/backend/data" "$EKCALL_HOME/app/frontend" "$UNIT_DIR"

# Paths the deploy script and the services need (the runner does not read ~/.bashrc).
cat > "$EKCALL_HOME/config.env" <<EOF
PYTHON=$PYTHON
NODE_BIN=$NODE_BIN
EOF

cat > "$UNIT_DIR/ekcall-backend.service" <<EOF
[Unit]
Description=Ek Call backend (FastAPI, port 8000)
After=network-online.target

[Service]
WorkingDirectory=$EKCALL_HOME/app/backend
ExecStart=$EKCALL_HOME/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1
Restart=on-failure
RestartSec=5
Environment=PYTHONUNBUFFERED=1
Environment=PYTHONIOENCODING=utf-8

[Install]
WantedBy=default.target
EOF

cat > "$UNIT_DIR/ekcall-frontend.service" <<EOF
[Unit]
Description=Ek Call app (built frontend, port 4173)
After=ekcall-backend.service

[Service]
WorkingDirectory=$EKCALL_HOME/app/frontend
ExecStart=$NODE_BIN/npm run preview -- --host 0.0.0.0 --port 4173 --strictPort
Restart=on-failure
RestartSec=5
Environment=PATH=$NODE_BIN:/usr/bin:/bin

[Install]
WantedBy=default.target
EOF

systemctl --user daemon-reload
systemctl --user enable ekcall-backend.service ekcall-frontend.service >/dev/null

echo "Set up $EKCALL_HOME (python: $PYTHON, node: $NODE_BIN)."
echo
echo "Still to do once (docs/deploy.md):"
echo "  1. cp backend/.env $EKCALL_HOME/app/backend/.env   (add http://localhost:4173 to FRONTEND_ORIGINS)"
echo "  2. cp -r backend/data/models $EKCALL_HOME/app/backend/data/   (e5, BanglaBERT, TF-IDF)"
echo "  3. sudo loginctl enable-linger $USER   (services keep running without a login)"
echo "  4. register the GitHub self-hosted runner with the label 'ekcall'"
