# CI and CD

- **CI** (`.github/workflows/ci.yml`) runs on GitHub's machines for every push and every pull request
  into `main`: `ruff check .` and `pytest -q` for the backend, `npm run lint` and `npm run build` for
  the app, at the same time. No secrets needed. A red CI blocks the deploy.
- **CD** (`.github/workflows/cd.yml`) runs on **our server** (a self-hosted GitHub runner) after CI
  passed on `main`, or by hand (GitHub, Actions, CD, "Run workflow"). It runs `deploy/deploy.sh`:
  1. `cd ~/Desktop/Comilla-University-Hackathon` and update it to `main` (`git reset --hard`):
     **uncommitted changes in that folder are discarded.** Git-ignored files are kept
     (`backend/.env`, `backend/data/`).
  2. `docker compose build backend`, then `docker compose up -d --wait` (from `backend/`). Compose
     replaces the backend container only when its image changed; Postgres and Chroma keep running.
     `--wait` fails the job if a container does not become healthy.
  3. Prints the backend container's health and `GET /health`.

The app itself is on Vercel, not on the server.

## What runs on the server

| Container | Port (this machine only) | Data |
|---|---|---|
| `ekcall-backend-1` (FastAPI, 1 worker) | 8000 | none: settings from `backend/.env`, models from `~/Desktop/models` (read-only) |
| `ekcall-postgres-1` | 5432 | Docker volume `ekcall_postgres-data` |
| `ekcall-chroma-1` | 8001 | Docker volume `ekcall_chroma-data` |

All three restart by themselves after a crash or a reboot. The volumes are outside the project folder:
deleting or re-cloning the folder keeps the data; only `docker compose down -v` deletes it.

ngrok (or the server's HTTPS address) points at port 8000; `PUBLIC_URL` and the Twilio webhook use it.

## One-time server setup

1. Docker and the project folder:
   ```
   sudo systemctl enable --now docker
   cd ~/Desktop && git clone https://github.com/Tamim2276/Comilla-University-Hackathon.git
   ```
2. Settings and models (they are not in git):
   - `backend/.env` from `backend/.env.example`, with the `POSTGRES_*`, `DATABASE_URL` and
     `CHROMA_*` lines filled in, and the Vercel address in `FRONTEND_ORIGINS`. Then
     `chmod 600 backend/.env`.
   - The models: `unzip ekcall_models.zip -d ~/Desktop` (gives `~/Desktop/models` with `router/`,
     `e5/` and `tfidf_router.joblib`).
3. First start and data (from `backend/`):
   ```
   docker compose up -d --build --wait
   docker compose exec backend python -m scripts.ingest           # documents into Chroma
   docker compose exec backend python -m scripts.prewarm --voice  # answer cache
   ```
   To move existing data from a laptop instead, see `scripts/migrate_to_servers.py`.
4. Register the runner. A repository admin (Tamim) opens GitHub, the repository, Settings, Actions,
   Runners, "New self-hosted runner", Linux x64, and follows the download and `./config.sh` steps
   shown there, with the label `ekcall`. Then, in the runner folder:
   ```
   sudo usermod -aG docker $USER   # the runner may use Docker
   sudo ./svc.sh install $USER
   sudo ./svc.sh start
   ```
5. First deploy: GitHub, Actions, CD, "Run workflow" on `main`. The first image build takes several
   minutes (PyTorch); later builds reuse it unless `requirements.txt` changed.

## Every day

From `~/Desktop/Comilla-University-Hackathon/backend`:
```
docker compose ps                  # all should say "healthy"
docker compose logs -f backend     # backend log
curl localhost:8000/health
```
Changed documents (`backend/data/raw_docs/`) are not re-ingested by the deploy. After such a deploy:
`docker compose exec backend python -m scripts.ingest`, then `... scripts.prewarm --voice`.

## Safety

- The CD job only runs for pushes to `main` of this repository, never for pull requests or forks,
  because it runs code on our own machine. Keep "Require approval for all outside collaborators" on in
  Settings, Actions, General.
- No secrets live in GitHub. The server keeps its own `backend/.env` (git-ignored, never in the image).
- Do not develop in the server's project folder: every deploy resets it to `main`.
