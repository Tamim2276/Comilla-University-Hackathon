# Team updates

What changed in `main` that affects Ragib or Ariful, newest first. Tamim adds an entry after every merge into `main`. Read the newest entries after each `git pull`, and do what the "You need to" lines say.

Nothing secret belongs in this file. Keys and Twilio values are shared privately.

---

## 8. Two more official documents in the search index, 21 Nov

**What changed**
- The birth registration rules (2018 gazette) and the 2004 Act now have real source links, so they are in the search index: birth registration went from 2 to 4 documents (49 searchable passages). Search finds the right service for 95.8 % of test questions now (was 94.8 %), and birth registration for 83 % (was 75 %). One more document (the FAQ) waits for its link.

**You need to**
1. Pull `main`, merge it into your branch, then in `backend/` run `python -m scripts.ingest` (about a minute) to rebuild your local search index. Without this your answers still use the old, smaller index.

**Good to know**
- Answers about birth registration may now cite the rules or the Act (a new source link in the checklist card and SMS).

---

## 7. Evaluation results, and 15 minutes of checking for you (D2-T3), 21 Nov

**What changed**
- `python -m scripts.eval_rag` measured the whole system against SRS 11 (results in `docs/results/rag_eval.md`): search finds the right service in the top 5 for 94.8 % of test questions (target 90 %), 37 of 37 off-topic questions got the safe FALLBACK answer (target 95 %), and phone answers take 3.4 s median (target 5 s).
- The last SRS target, answer correctness (90 %), needs people: `docs/results/answer_check.csv` holds 32 real answers to check.

**You need to** (Ragib takes rows 1 to 16, Ariful rows 17 to 32)
1. Open `docs/results/answer_check.csv` in Excel or Google Sheets (it is UTF-8, Bangla shows correctly).
2. For each of your rows, read `question`, `speech_text` and `checklist`, open the link in `sources`, and check the answer against the official page.
3. Write `yes` in `correct` if everything stated is right and it answers the question; `no` if anything is wrong, missing the point, or misleading, with a short note in `notes`. A `fallback` row is `yes` if the official documents really do not say it.
4. Save as CSV (UTF-8) and commit it on your branch, or send it to Tamim. He runs `python -m scripts.eval_rag --score`, which adds the result to the report.

**Good to know**
- Do not rerun `eval_rag` without `--score` after marking: it would refuse anyway, to protect your marks.

---

## 6. Question clusters API for the dashboard (D2-T2), 21 Nov

**What changed**
- `POST /api/v1/admin/clusters/rebuild` groups every logged question into topics: e5 embeddings, K-Means (k from 3 to 8 by silhouette score; a fixed 3 below 30 questions), and a short Bangla label per topic written by Gemini in one call (top keywords if Gemini is unavailable). It takes about 15 s for 100 questions. Response: `{"clusters": 8, "questions": 108, "labelled_by": "llm"}`.
- `GET /api/v1/admin/clusters` returns the stored topics, biggest first:
  `{"clusters": [{"id": 1, "label": "ভাতা পাওয়ার বয়সসীমা", "size": 19, "examples": ["...", "...", "..."]}]}`
  (`examples` holds up to 3 typical questions). Before the first rebuild the list is empty.
- Both need the `X-Admin-Token` header when `ADMIN_TOKEN` is set in `backend/.env`; without it they return 401 in the usual error JSON.

**You need to**
1. Pull `main` and merge it into your branch. No new settings.

**Good to know**
- Ariful (D2-R1, D2-R5): the cluster view calls these two routes; show the rebuild as a button with a loading state (it is slow). `routers/clusters.py` has its own copy of the token check for now. When your `require_admin_token` is in `routers/admin.py`, tell Tamim and he switches `clusters.py` to import yours (one line), so both admin routers share one check. Keep the same behaviour: no `ADMIN_TOKEN` set means open; otherwise the header must match.
- Clusters only exist after a rebuild, and they reflect the questions logged so far; rebuild after seeding the demo data (D2-R3).

---

## 5. BanglaBERT router (D2-T1), 21 Nov

**What changed**
- New router setting `ROUTER_BACKEND=banglabert` (now the default in `.env.example`). On our 108 hand-written test questions it routes 93.5 % correctly on its own (TF-IDF: 89.8 %), in about 35 ms, and it understands Banglish much better. Full results: `docs/results/router_eval.md`.
- If the BanglaBERT model folder is missing on a laptop, the app automatically uses TF-IDF. Nothing breaks.
- `/health` now names the router in use: `"router": "banglabert"`, `"tfidf"` or `"llm"` (as in SRS 8), instead of `"ok"`.

**You need to**
1. Pull `main` and merge it into your branch.
2. In `backend/.env` set `ROUTER_BACKEND=banglabert`. Without the model folder you keep TF-IDF, which is fine for your work.
3. Only the demo laptop needs the real model: Tamim shares the zipped `router` folder through Google Drive; unzip it to `backend/data/models/router/`.

**Good to know**
- Ariful: if the app or dashboard shows the `/health` result, the `router` value is now a name, not `ok`.
- Router choice does not change the API response shape; `router` in the chat response was already `banglabert` / `tfidf` / `llm` / `context`.

---

## 4. Answer cache and faster first question (D2-T4), 21 Nov

**What changed**
- A question that was answered before (same words, same service, same channel) is now answered from a cache for 24 hours: no LLM call, well under a second. Only `answered` results are cached; fallbacks and follow-up questions are not.
- The server now loads the router and search models in the background when it starts (`PRELOAD_MODELS=true`), so the first question is no longer 15 to 35 seconds. `/health` answers immediately while that happens.
- New script `python -m scripts.prewarm` fills the cache with the demo questions in `backend/data/questions/demo_questions.txt`. We run it before every rehearsal and before judging.
- `backend/app/main.py` got one new line (`container.warm_up()`). Nobody else needs to touch that file.

**You need to**
1. `git checkout main` then `git pull origin main`, then merge `main` into your own branch.
2. Add this line to your `backend/.env`: `PRELOAD_MODELS=true`
3. Restart the backend. In the log you should see `warm-up finished in ... s` after a few seconds.

**Good to know**
- Ragib: for phone calls, the transcript from Twilio rarely matches typed text exactly, so a repeated spoken question is only a cache hit if the words are identical. During rehearsal, ask each demo question once in a real call.
- Ariful: `GET /health` and the chat response shape are unchanged. The answer cache lives in the same SQLite database, so deleting `backend/data/ekcall.db` also clears it.

---

## 3. Grading, verifier and voice fast mode (D1-T5, D1-T6), 21 Nov

**What changed**
- The agent now grades the retrieved passages, rewrites the search query and tries again (at most 2 retries), and checks every claim against the official text before answering. If nothing reliable is left, the answer is exactly the fixed `FALLBACK` text.
- Phone calls (`channel=voice`) skip the grading step to save time: 2 LLM calls per question instead of 3.
- The answer can be a follow-up question (`status = follow_up`): the agent asks one short question, and the next turn keeps the same service even for a one-word reply such as "হ্যাঁ". It is rare, but Ragib's call flow and Ariful's chat page must handle that status (SRS 3.1 and 4.2).
- New folder `ml/` with the BanglaBERT training script. The trained router reaches 93.5 % on our test questions; it is plugged into the app in D2-T1.

**You need to**
1. `git pull origin main` and merge it into your branch. No new packages.

**Good to know**
- `speech_text` has at most 45 words and uses Bangla digits. On a call it ends with a sentence that details come by SMS, so only send the SMS when the status is `answered`.
- `checklist` fields the documents do not state are filled with `তথ্য পাওয়া যায়নি`. Show them as they are.
- `citations` has one entry per official document (title, URL, snippet).

---

## 2. Real agent in `main` (Checkpoint 1: D1-R4, D1-T4), 21 Nov

**What changed**
- `POST /api/v1/chat` now answers with the real agent: router, search in the official documents, a Bangla answer with a checklist and sources. The old fixed answer is gone, unless you ask for it.
- New setting `AGENT_ENGINE`: `langgraph` (the real agent, default) or `stub` (the old fixed old-age-allowance answer, needs no keys or models).
- New script `python -m scripts.ask "your question"` runs the agent once in the terminal. Add `--voice` for a phone-style answer.
- The router for now is TF-IDF, trained from `backend/data/questions/train.csv`.

**You need to**
1. `git pull origin main`, merge it into your branch.
2. In `backend/` with the venv active: `python -m scripts.train_baseline` (a few seconds; creates the router file, which is not in git).
3. Make sure `backend/.env` has a working LLM: the Gemini keys and model names from Tamim, or `LLM_BACKEND=ollama` with Ollama installed.
4. No keys yet, or the quota ran out? Put `AGENT_ENGINE=stub` in `.env` and keep building. Nothing else changes for you.
5. Test it: `python -m scripts.ask "আমার বয়স ৬৭, বয়স্ক ভাতা পাবো?"`

**Good to know**
- Answers take about 3 to 5 seconds once the models are loaded.
- Use `LLM_BACKEND=gemini` for real testing. `hybrid` hands grading and rewriting to a small local model that is weaker in Bangla, so answers get slower and vaguer.
- Test Bangla in Swagger (`http://localhost:8000/docs`) or the app, not with curl on Windows. In PowerShell run `$env:PYTHONIOENCODING = "utf-8"` before scripts that print Bangla.

---

## 1. New repository and team split, 21 Nov

- Work is split by feature: Tamim = AI/ML and the backend around it, Ragib = voice (phone and app), Ariful = web app, SMS, admin dashboard.
- Setup: `docs/SETUP.md`. Steps and owners: `docs/BUILD_PLAN.md` Section 0.1. Which files are yours: Section 0.4. Git workflow: Section 0.3.
