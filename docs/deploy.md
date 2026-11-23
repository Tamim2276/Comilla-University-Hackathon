# CI and CD

- **CI** (`.github/workflows/ci.yml`) runs on GitHub's machines for every push and every pull request
  into `main`: `ruff check .` and `pytest -q` for the backend, `npm run lint` and `npm run build` for
  the app. No secrets needed. A red CI blocks the deploy.
- **CD** (`.github/workflows/cd.yml`) runs on **our server** (a self-hosted GitHub runner) after CI passed
  on `main`. It runs `deploy/deploy.sh`, which:
  1. copies the new code to `~/ekcall/app` (the server's `.env`, database, Chroma store and models are
     never touched),
  2. installs Python and npm packages only when `requirements.txt` or `package-lock.json` changed,
  3. re-ingests the documents (then pre-warms the answer cache) only when `backend/data/raw_docs/` changed,
  4. builds the app (`npm run build`),
  5. restarts the two services and waits until `/health` and the app answer (the job fails otherwise).

  It can also be started by hand: GitHub, Actions, CD, "Run workflow".

For now the server is the laptop that runs the demo. The same setup works on a cloud VM later.

## Ports on the server

| Service | Port | Started by |
|---|---|---|
| `ekcall-backend` (uvicorn, 1 worker) | 8000 | systemd user service |
| `ekcall-frontend` (built app, `vite preview`) | 4173 | systemd user service |

ngrok keeps pointing at port 8000, so `PUBLIC_URL` and the Twilio webhook do not change. Open the app at
`http://localhost:4173`. While the services run, port 8000 is taken: to develop with `uvicorn --reload`,
first `systemctl --user stop ekcall-backend` (and `start` it again afterwards).

## One-time server setup

Run these on the server, from a clone of the repository.

1. Install the services and the `~/ekcall` folder:
   ```
   bash deploy/install.sh
   ```
2. Give the server its own settings and models (they are not in git):
   ```
   cp backend/.env ~/ekcall/app/backend/.env
   cp -r backend/data/models ~/ekcall/app/backend/data/
   ```
   In `~/ekcall/app/backend/.env`, add the built app to `FRONTEND_ORIGINS`:
   `FRONTEND_ORIGINS=http://localhost:5173,http://localhost:4173`
   Optional: copy `backend/data/ekcall.db` too, to keep the history and the answer cache.
3. Let the services run without a login session (once per machine):
   ```
   sudo loginctl enable-linger $USER
   ```
4. Register the runner. A repository admin (Tamim) opens GitHub, the repository, Settings, Actions,
   Runners, "New self-hosted runner", Linux x64, and follows the download and `./config.sh` steps
   shown there, with these answers:
   - labels: `ekcall`
   - work folder: default (`_work`)

   Then install it as a service so it starts with the machine (in the runner folder):
   ```
   sudo ./svc.sh install $USER
   sudo ./svc.sh start
   ```
5. First deploy: GitHub, Actions, CD, "Run workflow" on `main`. The first run takes 10 to 15 minutes
   (PyTorch and the other packages, then ingest and pre-warm). Later runs take about a minute.

## Every day

```
systemctl --user status ekcall-backend ekcall-frontend    # running?
journalctl --user -u ekcall-backend -f                    # backend log
cat ~/ekcall/DEPLOYED_SHA                                 # which commit is live
```

## Safety

- The CD job only runs for pushes to `main` of this repository, never for pull requests or forks, because it
  runs code on our own machine. Keep "Require approval for all outside collaborators" on in
  Settings, Actions, General.
- No secrets live in GitHub. The server keeps its own `backend/.env`; `deploy.sh` never prints it.
