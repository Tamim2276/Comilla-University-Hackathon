# Scenario check: S1 to S9 (D2-R3)

The acceptance scenarios of `docs/SRS.md` Section 10, run end to end on the demo setup.
Fill in the **Result** column with `pass`, `partial` or `fail`, and write what you saw in **Notes**.
A `partial` or `fail` gets a line in "Problems found" at the bottom with who fixes it.

## Setup of this run

SRS 11: every result must say which LLM produced it.

| Item | Value |
|---|---|
| Date and time | |
| Checked by | |
| Laptop | (demo laptop / Ariful / Ragib) |
| Commit (`git log --oneline -1`) | |
| `LLM_BACKEND`, `GEMINI_MODEL_MAIN`, `GEMINI_MODEL_FALLBACK` | |
| Router in use (`/health` → `router`) | |
| `AGENT_ENGINE` | must be `langgraph` |
| `SMS_BACKEND` | `textbee` for S1 and S3 (`console` only if textbee is not ready; then S3 is `partial`) |
| Twilio number and `PUBLIC_URL` (ngrok) | |
| Test phone (verified in Twilio) | |
| Answer cache | pre-warmed with `scripts.prewarm`: yes / no |

## Before you start (once, about 5 minutes)

1. `git checkout main`, `git pull origin main`.
2. In `backend/` (venv active, PowerShell: `$env:PYTHONIOENCODING = "utf-8"` first):
   - `python -m scripts.ingest`: fresh search index, also clears old cached answers.
   - `python -m scripts.seed_demo_data`: 60 sample questions for the dashboard (`is_demo = true`).
   - Optional, as for the real demo: `python -m scripts.prewarm`.
3. Start the backend (`uvicorn app.main:app --port 8000`), ngrok, and the app (`npm run dev`).
   Check `http://localhost:8000/health`: `db`, `llm`, `vector_db` are `ok`, `router` is `banglabert` or `tfidf`.
4. Use **one test phone number** for S1 to S6, so S5 and S6 can find what S1 to S4 did.
   For a clean start: Swagger `DELETE /api/v1/conversations/{phone}` with that number.
5. Open `http://localhost:5173/admin` in a second tab and note **Total questions** before S1: ______

## Results

| # | Scenario | Channel | Result | Notes |
|---|---|---|---|---|
| S1 | Elderly caller asks about old age allowance | phone | | |
| S2 | Follow-up question, "হ্যাঁ" keeps the service | phone | | |
| S3 | Exactly one SMS, at most 300 characters | SMS | | |
| S4 | Banglish NID question in the app | app | | |
| S5 | Family member opens History | app | | |
| S6 | Officer dashboard and clusters | admin | | |
| S7 | Out-of-scope question gets the FALLBACK | app + phone | | |
| S8 | Silent twice on a call | phone | | |
| S9 | Wrong Gemini key: Bangla error, no crash | app + `/health` | | |

---

## S1: Elderly caller (UC1)

**Do:** call the Twilio number from the test phone, or press **"Call me"** in the app. Ask:
> আমার বয়স ৬৭। আমি কি বয়স্ক ভাতা পাবো? কী কী লাগবে?

**Look for:**
- [ ] The greeting plays, then the answer starts within a few seconds (FR-CALL-10: a wait phrase is fine if it takes longer than 4 s).
- [ ] The answer is about **old age allowance**: the age rule (men 65+, women 62+), NID or birth registration needed, a short spoken answer.
- [ ] The call ends the answer with "আপনার মোবাইলে এসএমএস পাঠানো হয়েছে।" (TEAM_UPDATES 14).
- [ ] Backend log: `answered status=answered service=old_age_allowance ... channel=voice` and `SMS sent service=old_age_allowance`.
- [ ] Voice latency in the log (`latency_ms`): ______ ms (target: median at most 5 s).

**Result:** ______ **Notes:**

## S2: Follow-up (UC2)

**Do:** in the same call (or a new one), ask:
> বিধবা ভাতার জন্য কী লাগে?

If the agent asks back (for example about permanent residence), answer only:
> হ্যাঁ

**Look for:**
- [ ] Either a direct answer about **widow allowance**, or one short question back.
- [ ] After "হ্যাঁ" the answer is still about **widow allowance** (same service kept, FR-AGT-17).
- [ ] "হ্যাঁ" does **not** end the call.
- [ ] Backend log for the second turn: `service=widow_allowance`.

**Result:** ______ **Notes:** (write down whether the agent asked back or answered directly)

## S3: SMS (UC3)

**Do:** check the test phone after S1 (and after S2).

**Look for:**
- [ ] **Exactly one** SMS for old age allowance from S1, even if you ask about old age allowance again in the same call.
- [ ] S2 (another service) gives its own single SMS for widow allowance.
- [ ] The SMS starts with `এক কল: বয়স্ক ভাতা` and has the lines কারা / লাগবে / ফি / কোথায় / সূত্র (SRS 3.2).
- [ ] At most **300 characters**. The console log prints the length: `... chars`. Length: ______
- [ ] The spoken answer was not delayed by the SMS (it is sent in the background, FR-SMS-04).

**Result:** ______ **Notes:**

## S4: App (UC4)

**Do:** in the app, start with the test phone number and type:
> NID-te namer banan bhul, ki korbo?

**Look for:**
- [ ] The service tag says **এনআইডি সংশোধন** (`nid_correction`).
- [ ] A checklist card (কারা পাবেন, কী কী লাগবে, ফি, কোথায় আবেদন, সিদ্ধান্ত).
- [ ] **At least one source link** under the card, and it opens the official page.
- [ ] The play button reads the answer aloud (Ragib's D2-R2).

**Result:** ______ **Notes:**

## S5: Family (UC5)

**Do:** in the app, open **আগের উত্তর** with the same phone number as S1. (For the family story: open the app in another browser or a private window, enter the S1 number, then আগের উত্তর.)

**Look for:**
- [ ] The **old age allowance** checklist from the S1 phone call is listed, with the badge **"এসএমএস পাঠানো হয়েছে"**.
- [ ] The S2 and S4 checklists are there too, newest first.

**Result:** ______ **Notes:**

## S6: Officer (UC6)

**Do:** open `http://localhost:5173/admin` (with `VITE_ADMIN_TOKEN` set). Press **"আবার গ্রুপ করুন"** and wait.

**Look for:**
- [ ] **Total questions** is higher than the number you noted before S1 (S1 to S5 are counted): before ______ now ______
- [ ] "কোথা থেকে প্রশ্ন" shows both phone calls and the app.
- [ ] The S1 to S4 questions appear in "সাম্প্রতিক প্রশ্ন" without the "নমুনা" badge.
- [ ] Clusters appear with sensible Bangla labels (for example NID spelling, allowance age). Number of clusters: ______ labelled by Gemini or keywords: ______
- [ ] The unanswered list is visible (S7 adds to it).
- [ ] The numbers change by themselves within 10 s after a new question (FR-ADM-06).

**Result:** ______ **Notes:**

## S7: Exception

**Do:** ask in the app (and once on a call, if time allows):
> প্রতিবেশীর সাথে জমি নিয়ে ঝামেলা, কী করবো?

**Look for:**
- [ ] The answer is **exactly** the FALLBACK text:
  "দুঃখিত, এই বিষয়ে সরকারি কাগজে আমি নিশ্চিত তথ্য পাইনি। দয়া করে ৩৩৩ নম্বরে ফোন করুন অথবা উপজেলা অফিসে যোগাযোগ করুন।"
- [ ] No checklist card and no SMS.
- [ ] The question appears in the dashboard's **unanswered** list within 10 s (logged as `fallback`).

**Result:** ______ **Notes:**

## S8: Robustness

**Do:** call the number. After the greeting, say nothing. After the second prompt, say nothing again.

**Look for:**
- [ ] First silence: "দুঃখিত, আমি শুনতে পাইনি। আবার বলবেন?" (REPROMPT).
- [ ] Second silence: "ধন্যবাদ। ভালো থাকবেন।" (GOODBYE), then the call hangs up (FR-CALL-04).

**Result:** ______ **Notes:**

## S9: Failure

**Do:**
1. In `backend/.env`, change `GEMINI_API_KEYS` to a wrong value (keep the real one somewhere safe, never in a chat or a commit).
2. Restart the backend. Wait about a minute (the `/health` LLM check is cached for 60 s), then open `/health`.
3. In the app, ask a question that is **not** a demo question (cached answers would still work), for example:
   > জন্ম নিবন্ধন সংশোধন করতে কত দিন লাগে?
4. Put the real key back and restart the backend.

**Look for:**
- [ ] `/health` shows `"llm": "error"`, and the server keeps running.
- [ ] The app shows the Bangla error bubble: "দুঃখিত, এখন একটু সমস্যা হচ্ছে। একটু পরে আবার চেষ্টা করুন অথবা ৩৩৩ নম্বরে ফোন করুন।"
- [ ] No stack trace in the app; the log has a short `LLM_UNAVAILABLE` line.
- [ ] Optional on a call: the caller hears the same ERROR text and the call stays polite (NFR-REL-01).
- [ ] After the real key is back, `/health` shows `"llm": "ok"` again.

**Result:** ______ **Notes:**

---

## Extra checks (app, SMS, admin)

| Check | How | Result | Notes |
|---|---|---|---|
| Wrong phone number on the start page | type `0123` → Bangla INVALID_PHONE message | | |
| Admin token | wrong `VITE_ADMIN_TOKEN` → Bangla admin-token message; Swagger without the header → 401 | | |
| "Call me" twice | second press within 60 s → Bangla wait message (FR-CALL-07) | | |
| Offline notice | DevTools → Network → Offline → red notice; back online → green note | | |
| 360 px | DevTools device toolbar, width 360: start, chat, history, admin | | |
| Install as app | Chrome install icon → opens with the flag icon and the name "এক কল" | | |
| Sample data | dashboard rows from `seed_demo_data` show the "নমুনা" badge; say so in the demo | | |

## Problems found

| # | Scenario | What happened | Who fixes it | Fixed? |
|---|---|---|---|---|
| 1 | | | | |

## After the run

- `python -m scripts.seed_demo_data` again if the sample rows were cleared.
- Put the real Gemini key back (S9) and restart the backend.
- Commit this file on your branch: `git add docs/results/scenario_check.md`.
