#!/usr/bin/env python3
"""Parse README.md program tables into catalog.json, then extract structured
requirements per program with a free model (NVIDIA NIM by default).

Requirements are read from the list's own Eligibility/Notes text, so every field is
`source: list-text` until a human or agent verifies it on the official page
(`verified_on` stays null). Unknown stays "unknown"; it is never guessed as false.

Usage: NVIDIA_API_KEY=... python3 planner/build_catalog.py [--model M] [--limit N]
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "planner" / "catalog.json"

FIELDS = {
    "self_serve": "bool|unknown - anyone can apply online without a referral",
    "requires_company_domain_email": "bool|unknown",
    "requires_website": "bool|unknown",
    "requires_incorporation": "bool|unknown - legal entity (LLC/C-corp etc.)",
    "requires_vc_or_accelerator": "bool|unknown - for the tier described",
    "requires_funding": "bool|unknown - raised money / within N months of a round",
    "requires_payment_method": "bool|unknown",
    "requires_paid_product": "bool|unknown - e.g. a bank account or paid plan first",
    "unlocks": "list of other programs this unlocks or improves",
    "entry_tier_usd": "number|null - credits at the easiest tier",
    "max_tier_usd": "number|null",
    "region_limited": "string|null",
}

PROMPT = """Extract eligibility facts for one startup-credit program from a curated list row.
Answer ONLY with a JSON object with exactly these keys: {fields}.
Use "unknown" when the row does not say. Do not use outside knowledge.
Row: {row}"""


def parse_readme() -> list[dict]:
    progs, cat = [], None
    for line in (ROOT / "README.md").read_text().splitlines():
        if line.startswith("## "):
            cat = line[3:].strip()
        if not line.startswith("| **["):
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        m = re.match(r"\*\*\[(.+?)\]\((.+?)\)\*\*", cells[0])
        if not m:
            continue
        progs.append({
            "program": m.group(1), "url": m.group(2), "category": cat,
            "credits": cells[1] if len(cells) > 1 else "",
            "eligibility": cells[2] if len(cells) > 2 else "",
            "notes": cells[3] if len(cells) > 3 else "",
        })
    return progs


def ask(model: str, row: str, key: str) -> dict:
    body = {
        "model": model,
        "messages": [{"role": "user", "content": PROMPT.format(fields=json.dumps(FIELDS), row=row)}],
        "max_tokens": 4096, "temperature": 0,
    }
    req = urllib.request.Request(
        "https://integrate.api.nvidia.com/v1/chat/completions", data=json.dumps(body).encode(),
        headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json", "User-Agent": "credits-planner/0.1"})
    err = "retries exhausted"
    for attempt in range(4):
        try:
            r = json.load(urllib.request.urlopen(req, timeout=180))
            txt = r["choices"][0]["message"]["content"] or ""
            m = re.search(r"\{.*\}", txt, re.S)
            return json.loads(m.group(0)) if m else {"_error": "no json"}
        except urllib.error.HTTPError as e:
            if e.code == 429:
                time.sleep(15 * (attempt + 1)); continue
            return {"_error": f"http {e.code}"}
        except Exception as e:  # noqa: BLE001
            err = str(e)
            time.sleep(5)
    return {"_error": err}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="nvidia/nemotron-3-ultra-550b-a55b")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    key = os.environ.get("NVIDIA_API_KEY")
    if not key:
        sys.exit("NVIDIA_API_KEY not set")
    progs = parse_readme()
    if a.limit:
        progs = progs[: a.limit]
    prev = {p["program"]: p for p in json.loads(OUT.read_text())["programs"]} if OUT.exists() else {}
    for i, p in enumerate(progs):
        old = prev.get(p["program"], {})
        if old.get("requirements") and not old["requirements"].get("_error") and old.get("eligibility") == p["eligibility"]:
            p["requirements"] = old["requirements"]
        else:
            row = f"{p['program']} ({p['category']}): credits={p['credits']}; eligibility={p['eligibility']}; notes={p['notes']}"
            p["requirements"] = ask(a.model, row, key)
            time.sleep(1.6)  # stay under NIM's 40 RPM
        p["source"] = "list-text"
        p["verified_on"] = old.get("verified_on")
        OUT.write_text(json.dumps({"model": a.model, "built": time.strftime("%Y-%m-%d"), "partial": True, "programs": progs[: i + 1]}, indent=1))
        print(f"{i+1}/{len(progs)} {p['program']}: {'ERR ' + p['requirements']['_error'] if '_error' in p['requirements'] else 'ok'}", flush=True)
    OUT.write_text(json.dumps({"model": a.model, "built": time.strftime("%Y-%m-%d"), "programs": progs}, indent=1))
    print(f"wrote {OUT} ({len(progs)} programs)")


if __name__ == "__main__":
    main()
