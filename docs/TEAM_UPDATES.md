# Team updates

What changed in `main` that affects Ragib or Ariful, newest first. Tamim adds an entry after every merge into `main`. Read the newest entries after each `git pull`, and do what the "You need to" lines say.

Nothing secret belongs in this file. Keys and Twilio values are shared privately.

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
