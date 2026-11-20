"""Make router training data from the hand-written seeds (D1-R4, FR-DATA-05).

Run from backend/:
    python -m scripts.augment_questions                    # uses LLM_BACKEND from .env
    python -m scripts.augment_questions --backend ollama   # saves Gemini quota
    python -m scripts.augment_questions --fresh            # ignore saved LLM answers

Steps:
1. Split the seeds 90/10 into train and val **by seed** (per label), before any paraphrasing,
   so variants of one seed never land on both sides.
2. Ask the fast model for 8 variants of each seed (5 seeds per call): casual speech, spelling
   mistakes, Banglish, speech-recognition errors, short, long.
3. Drop variants with letters from other scripts, duplicates, and anything that equals a
   test.csv question (test.csv stays untouched).
4. Write data/questions/train.csv and val.csv (`text,label`), seeds included.

LLM answers are saved in data/models/augment_cache.json (git-ignored), so a failed run
continues where it stopped instead of paying for the same calls again.
"""

import argparse
import csv
import json
import logging
import random
import re
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

from app.application.ports.llm import LLM, ModelRole
from app.config import BACKEND_DIR, Settings
from app.container import Container
from app.domain.errors import LLMUnavailable

QUESTIONS_DIR = BACKEND_DIR / "data" / "questions"
CACHE_FILE = BACKEND_DIR / "data" / "models" / "augment_cache.json"
VARIANTS_PER_SEED = 8
SEEDS_PER_CALL = 5
VAL_SHARE = 0.10
RANDOM_SEED = 42
# Bangla letters, English letters, digits, spaces, common punctuation, danda, zero-width joiners.
_ALLOWED = re.compile(r"^[ঀ-৿।॥‌‍ -~\s]+$")

PROMPT = """You create training data for a Bangla question classifier used by a phone helpline for
Bangladesh government services. Rewrite each question below in {n} different ways, the way real
citizens would say or type it. Keep the SAME meaning and the SAME topic, so the label stays correct.
Mix these styles across the {n} variants:
1. casual spoken Bangla (village or city speech, polite or blunt)
2. common spelling mistakes in Bangla
3. Banglish: Bangla written in English letters, or Bangla mixed with English words
4. speech-recognition style errors (words merged or split, a similar-sounding wrong word, no punctuation)
5. very short (3 to 5 words)
6. long, with a little personal background
Rules: every variant is different from the original and from the others; numbers may be Bangla or
English digits; never add facts about fees or rules; return only JSON.

Questions:
{items}"""

SCHEMA = {
    "type": "object",
    "properties": {
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "integer"},
                    "variants": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["id", "variants"],
            },
        }
    },
    "required": ["items"],
}


def read_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def norm_key(text: str) -> str:
    """Comparison key for de-duplication: same letters, ignoring case, spaces and punctuation."""
    text = unicodedata.normalize("NFC", text).lower()
    text = re.sub(r"[\s।?!.,;:'\"()\-]+", " ", text)
    return text.strip()


def split_seeds(seeds: list[dict[str, str]]) -> tuple[list[dict[str, str]], list[dict[str, str]]]:
    """90/10 per label, at least one val seed per label. Same result every run."""
    by_label: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in seeds:
        by_label[row["label"]].append(row)
    rng = random.Random(RANDOM_SEED)
    train, val = [], []
    for label in sorted(by_label):
        rows = by_label[label][:]
        rng.shuffle(rows)
        n_val = max(1, round(len(rows) * VAL_SHARE + 0.01))  # 15 seeds -> 2 val seeds
        val += rows[:n_val]
        train += rows[n_val:]
    return train, val


def load_cache(fresh: bool) -> dict[str, list[str]]:
    if fresh or not CACHE_FILE.exists():
        return {}
    return json.loads(CACHE_FILE.read_text(encoding="utf-8"))


def save_cache(cache: dict[str, list[str]]) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    CACHE_FILE.write_text(json.dumps(cache, ensure_ascii=False, indent=1), encoding="utf-8")


def ask_variants(llm: LLM, batch: list[str]) -> dict[int, list[str]]:
    items = "\n".join(f"{i}. {text}" for i, text in enumerate(batch))
    prompt = PROMPT.format(n=VARIANTS_PER_SEED, items=items)
    data = llm.generate_json(prompt, SCHEMA, role=ModelRole.FAST, temperature=0.9)
    out: dict[int, list[str]] = {}
    for item in data.get("items", []):
        idx = item.get("id")
        if isinstance(idx, int) and 0 <= idx < len(batch):
            out[idx] = [v.strip() for v in item.get("variants", []) if isinstance(v, str) and v.strip()]
    return out


def augment(llm: LLM, seeds: list[dict[str, str]], cache: dict[str, list[str]]) -> int:
    """Fills `cache[seed_text]` for every seed that has no variants yet. Returns failed calls."""
    todo = [row["text"] for row in seeds if not cache.get(row["text"])]
    failures = 0
    for start in range(0, len(todo), SEEDS_PER_CALL):
        batch = todo[start : start + SEEDS_PER_CALL]
        try:
            result = ask_variants(llm, batch)
        except LLMUnavailable as exc:
            failures += 1
            print(f"  call failed ({exc}); rerun the script later to fill the gap")
            continue
        for idx, text in enumerate(batch):
            if result.get(idx):
                cache[text] = result[idx]
        save_cache(cache)
        done = len(todo) if start + SEEDS_PER_CALL >= len(todo) else start + SEEDS_PER_CALL
        print(f"  {done}/{len(todo)} seeds paraphrased")
    return failures


def build_rows(
    seeds: list[dict[str, str]], cache: dict[str, list[str]], blocked: set[str]
) -> list[dict[str, str]]:
    """Seeds + their variants, without duplicates and without anything from test.csv."""
    seen = set(blocked)
    rows: list[dict[str, str]] = []
    for seed in seeds:
        for text in [seed["text"], *cache.get(seed["text"], [])]:
            key = norm_key(text)
            if not key or key in seen or not _ALLOWED.match(text):
                continue
            seen.add(key)
            rows.append({"text": text, "label": seed["label"]})
    return rows


def write_rows(path: Path, rows: list[dict[str, str]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["text", "label"])
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", choices=["gemini", "ollama", "hybrid"], default=None)
    parser.add_argument("--fresh", action="store_true", help="ignore saved LLM answers")
    args = parser.parse_args()
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")

    settings = Settings(**({"llm_backend": args.backend} if args.backend else {}))  # type: ignore[arg-type]
    llm = Container(settings).llm
    seeds = read_rows(QUESTIONS_DIR / "seed.csv")
    test_keys = {norm_key(row["text"]) for row in read_rows(QUESTIONS_DIR / "test.csv")}
    train_seeds, val_seeds = split_seeds(seeds)
    print(f"LLM_BACKEND = {settings.llm_backend}")
    print(f"seeds: {len(seeds)} -> train {len(train_seeds)}, val {len(val_seeds)} (split by seed)")

    cache = load_cache(args.fresh)
    failures = augment(llm, train_seeds + val_seeds, cache)

    val_rows = build_rows(val_seeds, cache, blocked=test_keys)
    # Train must not repeat a val sentence either, so val keys are blocked too.
    train_rows = build_rows(train_seeds, cache, blocked=test_keys | {norm_key(r["text"]) for r in val_rows})
    write_rows(QUESTIONS_DIR / "train.csv", train_rows)
    write_rows(QUESTIONS_DIR / "val.csv", val_rows)

    missing = [row["text"] for row in seeds if not cache.get(row["text"])]
    print(f"train.csv: {len(train_rows)} rows   val.csv: {len(val_rows)} rows")
    per_label: dict[str, int] = defaultdict(int)
    for row in train_rows:
        per_label[row["label"]] += 1
    print("train rows per label: " + ", ".join(f"{k} {v}" for k, v in sorted(per_label.items())))
    if missing or failures:
        print(f"WARNING: {len(missing)} seeds have no variants yet ({failures} failed calls). Run again.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
