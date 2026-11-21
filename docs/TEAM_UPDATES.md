# Team updates

What changed in `main` that affects Ragib or Ariful, newest first. Tamim adds an entry after every merge into `main`. Read the newest entries after each `git pull`, and do what the "You need to" lines say.

Nothing secret belongs in this file. Keys and Twilio values are shared privately.

---

## Start here: everything to do once, in order (Ragib and Ariful)

Do these steps first. The numbered entries below (newest first, 11 down to 1) explain what changed and why; read them from the top until you reach one you already read.

**1. Get the latest code**
- `git checkout main`, then `git pull origin main`.
- Already have a branch? `git checkout <your-branch>`, then `git merge main`. New step? `git checkout -b <your-name>/<step>-<short-name>` (Section 0.3 of `docs/BUILD_PLAN.md`). Run git commands from the project root.

**2. Set up your laptop** (skip what is already done): `docs/SETUP.md` sections 1 to 6 (tools, venv, requirements). Troubleshooting: section 10.

**3. Fill your `backend/.env`** (write each value right after the `=`, no comment on the same line)
- From Tamim, privately: `GEMINI_API_KEYS`, `GEMINI_MODEL_MAIN=gemini-3.5-flash-lite`, `GEMINI_MODEL_FAST=gemini-3.5-flash-lite`. Also set `LLM_BACKEND=gemini`.
- Add these: `PRELOAD_MODELS=true`, `ROUTER_BACKEND=banglabert` (without the model folder it falls back to TF-IDF by itself), `AGENT_ENGINE=langgraph`.
- No keys yet, or the key limit is reached? Use `AGENT_ENGINE=stub` (a fixed sample answer) and keep building. Nothing else changes for you.
- Never commit `.env`, never paste keys into a chat that keeps history.

**4. Build the search index and the router** (`backend/` folder, venv active, PowerShell: first `$env:PYTHONIOENCODING = "utf-8"`)
- `python -m scripts.train_baseline` (seconds; makes the TF-IDF router).
- `python -m scripts.ingest` (about a minute; builds the search index from the official documents and clears old cached answers). **Run it again after every pull that changes `backend/data/raw_docs/`.**

**5. Check that it works**
- `python -m scripts.ask "আমার বয়স ৬৭, বয়স্ক ভাতা পাবো?"` prints a Bangla answer with sources (first run takes longer while models load).
- `ruff check .` and `pytest -q` are green.
- `uvicorn app.main:app --reload --port 8000`, then open `http://localhost:8000/health`: every part says ok (the router says banglabert or tfidf). Test Bangla in Swagger (`http://localhost:8000/docs`), not with curl.

**6. Your own steps** (Section 0.1 of `docs/BUILD_PLAN.md`, Owner column, in that order)
- **Ragib:** start with D1-A3 (Twilio echo mode). Twilio values come from Tamim privately. Entry 3 explains the `follow_up` answer status, which your call flow must handle ("হ্যাঁ" after a follow-up keeps the same service). **Read entry 12 before you touch Twilio:** the number is a shared trial number (it is not under "Active numbers", that is normal), the webhook is set under Try out Voice > Receive a call, and only verified phones can call in.
- **Ariful:** start with D1-R3 (app pages and chat page). Entry 6 has the JSON of the two cluster routes for your cluster view. Entries 9 and 10 say checklists can now be longer (several amounts, longer paper lists): wrap them on the card and keep the SMS within 300 characters.

**7. When you finish a step**
- Run the step's Done-check, `ruff check .`, `pytest -q` (and `npm run build` if you touched the app).
- Name the step in your pull request title, change only files you own (Section 0.4), never edit `main.py`, `schemas.py`, `deps.py` or `docs/SRS.md`.
- Tell Tamim, so he can update the Status column and add an entry here.

**What Tamim gives you privately (not in this file)**
- Gemini keys and model names; the Twilio values and your verified number (Ragib); access to the repo (collaborator invitation).
- The BanglaBERT router folder (about 450 MB, for the demo laptop only) when it is time.

**Your first task together (about 15 minutes each)**
- Mark the answer check (entry 7): Ragib rows 1 to 16, Ariful rows 17 to 32 of `docs/results/answer_check.csv`. Do it after step 5 above, so you have the same documents. Send your marked file to Tamim (or commit it on your branch).

**Later**
- Later, deployment: Ariful puts the app on Vercel (set `VITE_API_URL` to the backend address Tamim gives you); the backend runs on the demo laptop with ngrok. Details when the time comes.

---

## 12. Twilio: the trial number is shared, how to set its webhook (Ragib), 21 Nov

**What changed**
- Nothing in the code. The Twilio number in `.env` is a **shared trial number**, so it is not listed under Phone Numbers > Active numbers and the API does not list it. That is why a lookup says "number not found" even though the account ID and token match and calls from the number work.

**You need to** (Ragib, when your voice server is running)
1. Start `ngrok http 8000` and set `PUBLIC_URL` in `backend/.env` to its address.
2. Twilio Console (Tamim's account, so Tamim does this or shares his screen): **Try out Voice > Receive a call > Custom > Webhook URL** `https://<your-ngrok-url>/voice/incoming`, POST, Save. Only one webhook exists at a time, so it points to the laptop that is testing.
3. Phones that call in must be **verified recipients** in the console (about 5 allowed). Ask Tamim to add yours and Ariful's.
4. Expect a Twilio trial message first, and calls last at most 10 minutes.

**Good to know**
- "Call me" (outbound) uses the same number as the From number and the values already in `.env`; it needs the recipient to be a verified number too.
- Troubleshooting rows for this are in `docs/BUILD_PLAN.md` Section 9.
- Check your setup quickly: the account ID and token are fine if the console works with them; "number not found" in a lookup is expected for a trial number, so do not spend time on it. If a call fails, look at Twilio Console > Monitor > Logs > Errors and match the code with the Section 9 table.

**Limits of the trial number (know them before the demo)**
- Only **verified phones** can call the number or receive "Call me": Tamim's, yours, Ariful's (about 5 allowed). A judge's own phone will not get through unless it is added or the account is upgraded.
- A Twilio trial message plays first, and a call lasts at most 10 minutes.
- The number has **one** incoming webhook, so it reaches one laptop at a time. Say in the group chat who is testing, and update the webhook and `PUBLIC_URL` when the voice laptop changes (the demo laptop at the end).

**Backup plan if calls do not work (decided, no extra work)**
1. Spend at most 1 hour on Twilio problems on Day 2 morning (Section 9 of the plan).
2. Demo the voice through the app: the browser microphone (Bangla speech-to-text) and the spoken answer (text-to-speech). It is the same agent and the same answers; only the phone line is missing. Ragib's D1-R7 (mic) and D2-R2 (answer audio) are the steps that make this work, so they matter for the demo.
3. Tamim makes the live phone call himself from a verified phone, and the "Call me" button in the app rings a verified phone.
4. Record the 3-minute backup video of the phone call (S1) whenever it works (D2-ALL-2).

---

## 11. Trade licence: Dhaka South added, 21 Nov

**What changed**
- Trade licence now has two city corporations: Dhaka North (already there) and Dhaka South (new: how to apply, the papers, 3 days or 7 days, renewal at a Sonali Bank branch in 1 day, the online link). Answers say which corporation a rule belongs to; neither page gives a licence fee amount, so the agent says the fee depends on the type of business and does not invent a number.

**You need to**
1. Pull `main`, merge it into your branch, then in `backend/` run `python -m scripts.ingest`.

**Good to know**
- Trade licence checklists may show the fee as "depends on the type of business" or the standard unknown text. That is the honest answer with these documents.

---

## 10. Land mutation: required papers, appeals and the Ministry circular in the search index, 21 Nov

**What changed**
- Land mutation (e-Namjari) went from 1 to 3 official documents (25 searchable passages, was 3): the Ministry of Land's FAQ page (the list of required papers, fees, the 28-day target, hearing, tracking, appeals and review deadlines) and the ministry circular of 4 December 2022 on how applications are decided.
- Questions such as "which papers do I need", "where do I appeal if my application is rejected" and "does an heir certificate expire" now get answers with the official source. The circular says an heir certificate has no expiry, which replaces older guides.

**You need to**
1. Pull `main`, merge it into your branch, then in `backend/` run `python -m scripts.ingest` (about a minute). It also clears your old cached answers.

**Good to know**
- Nothing changes in the API. Checklist `papers` for land mutation is now a real list, so the checklist card and the SMS will show more lines (the SMS formatter already shortens long lines).

---

## 9. NID: official fee table and form instructions in the search index, 21 Nov

**What changed**
- NID correction went from 5 to 12 documents (35 searchable passages, was 17), all from the Election Commission (ecs.gov.bd): the official fee table, the instructions of the correction form (which papers each kind of correction needs), the lost-card form with its instructions, and the forms for printing mistakes, moving the voter area and correcting or removing voter-list entries.
- Questions about NID fees now get the real amounts with VAT, for example the first name correction costs fee 200 Taka plus 30 Taka VAT, and the source link in the answer is the Election Commission's fee table. Before, the answer only said that a fee exists.
- Questions about papers (date of birth, name, parents' names, address, blood group) now cite the instructions of the correction form.

**You need to**
1. Pull `main`, merge it into your branch, then in `backend/` run `python -m scripts.ingest` (about a minute). It also clears your old cached answers.

**Good to know**
- Ariful: an NID answer's checklist `fee` can now be a longer text with several amounts (1st, 2nd, later time). Make sure the checklist card and the SMS text wrap it properly (the SMS formatter already shortens long lines).

---

## 8. Birth registration documents complete, search index rebuilt, 21 Nov

**What changed**
- The birth registration rules (2018 gazette), the 2004 Act and the FAQ now have real source links, so all 5 birth registration documents are in the search index (58 searchable passages, was 2 documents). Search finds the right service for 97.9 % of test questions now (was 94.8 %), and for birth registration 100 % (was 75 %). A question that used to get the "no confident information" reply (birth number not 17 digits) now gets a real answer with the FAQ as its source.
- `python -m scripts.ingest` now also clears the answer cache, so answers made from old documents are never served after the documents change.

**You need to**
1. Pull `main`, merge it into your branch, then in `backend/` run `python -m scripts.ingest` (about a minute) to rebuild your local search index and clear your old cached answers. Without this your answers still use the old, smaller index.

**Good to know**
- Answers about birth registration may now cite the rules or the Act (a new source link in the checklist card and SMS).

---

## 7. Evaluation results, and 15 minutes of checking for you (D2-T3), 21 Nov

**READY: please mark your rows now.** `docs/results/answer_check.csv` was regenerated at the end of 21 Nov with the final documents (it replaces the first version; if you opened an older copy, discard it).

**What changed**
- `python -m scripts.eval_rag` measured the whole system against SRS 11 (results in `docs/results/rag_eval.md`, final run): search finds the right service in the top 5 for 96.9 % of test questions (target 90 %), 37 of 37 off-topic questions got the safe FALLBACK answer (target 95 %), and phone answers take about 3.6 to 5.1 s median depending on how busy Gemini is (target 5 s).
- The last SRS target, answer correctness (90 %), needs people: `docs/results/answer_check.csv` holds 32 real answers to check (29 answered, 3 safe fallbacks).

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
