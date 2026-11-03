#!/usr/bin/env python3
"""Match catalog.json against owner-profile.yaml and print an action plan.

Buckets:
  file_now   - nothing in the row conflicts with the owner's constraints
  ask_first  - a requirement is unknown in the row OR in the owner profile
  blocked    - a known requirement the owner does not meet; lists what unlocks it
The list's own Application Tips say a company-domain email is the #1 rejection reason,
so programs whose domain requirement is unknown are flagged `domain_risk`.
Writes planner/plan.json and prints a short table.
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_profile() -> dict:
    prof = {}
    for line in (ROOT / "planner/owner-profile.yaml").read_text().splitlines():
        m = re.match(r"^([a-z_]+):\s*([^#\n]*?)\s*(#.*)?$", line)
        if m and m.group(2):
            v = m.group(2).strip()
            prof[m.group(1)] = {"true": True, "false": False}.get(v, v)
    return prof


# requirement key -> (profile key, human label of the unlock)
GATES = {
    "requires_company_domain_email": ("has_company_domain", "company domain + email"),
    "requires_website": ("has_website", "public product website"),
    "requires_incorporation": ("incorporated", "legal entity"),
    "requires_vc_or_accelerator": ("has_vc_or_accelerator", "VC/accelerator affiliation"),
    "requires_funding": ("has_funding", "a funding round"),
    "requires_payment_method": ("willing_to_add_payment_method", "a payment method (owner approval)"),
    "requires_paid_product": ("willing_to_add_payment_method", "a paid product/bank account (owner approval)"),
}


def main() -> None:
    prof = load_profile()
    cat = json.loads((ROOT / "planner/catalog.json").read_text())
    vpath = ROOT / "planner/verified.json"
    verified = {k: v for k, v in json.loads(vpath.read_text()).items() if not k.startswith("_")} if vpath.exists() else {}
    plan = []
    for p in cat["programs"]:
        r = dict(p.get("requirements", {}))
        if p["program"] in verified:
            v = verified[p["program"]]
            r.update(v["requirements"])
            p["verified_on"] = v["verified_on"]
        blocked, unknown = [], []
        if r.get("_error"):
            unknown.append("not classified")
        for req, (pk, label) in GATES.items():
            need, have = r.get(req, "unknown"), prof.get(pk, "unknown")
            if need is True and have is False:
                blocked.append(label)
            elif need is True and have == "unknown":
                unknown.append(label)
            elif need == "unknown" and have is False and req in ("requires_payment_method", "requires_company_domain_email"):
                unknown.append(label + "?")
        if r.get("self_serve") is False and not blocked:
            unknown.append("referral/partner only?")
        bucket = "blocked" if blocked else ("ask_first" if unknown else "file_now")
        plan.append({
            "program": p["program"], "url": p["url"], "category": p["category"], "bucket": bucket,
            "entry_usd": r.get("entry_tier_usd"), "max_usd": r.get("max_tier_usd"),
            "blocked_by": blocked, "unknowns": unknown, "unlocks": r.get("unlocks") or [],
            "domain_risk": r.get("requires_company_domain_email") != False,  # noqa: E712
            "verified_on": p.get("verified_on"),
        })
    order = {"file_now": 0, "ask_first": 1, "blocked": 2}
    plan.sort(key=lambda x: (order[x["bucket"]], -(x["entry_usd"] or 0) if isinstance(x["entry_usd"], (int, float)) else 0))
    (ROOT / "planner/plan.json").write_text(json.dumps({"profile": prof, "plan": plan}, indent=1))
    c = Counter(x["bucket"] for x in plan)
    print(f"programs={len(plan)} file_now={c['file_now']} ask_first={c['ask_first']} blocked={c['blocked']}")
    unlock = Counter(b for x in plan for b in x["blocked_by"])
    print("biggest unlocks (programs blocked by each):", dict(unlock.most_common()))
    for x in plan:
        if x["bucket"] != "blocked":
            print(f"  {x['bucket']:9} {x['program'][:42]:42} entry={x['entry_usd']} {'DOMAIN-RISK ' if x['domain_risk'] else ''}{'; '.join(x['unknowns'])[:70]}")


if __name__ == "__main__":
    main()
