# Credits planner

Turns this list into a filing plan that respects the applicant's real constraints
(no company domain yet, not incorporated, no VC, no spending without approval).

```
NVIDIA_API_KEY=... python3 planner/build_catalog.py   # README tables -> catalog.json (free NIM model extracts requirements)
python3 planner/plan.py                               # catalog.json x owner-profile.yaml -> plan.json
```

- `owner-profile.yaml` - the constraints. `unknown` means "ask before filing".
- `catalog.json` - one entry per program. `requirements` come from the list's own row
  text (`source: list-text`), so they are hints. `verified_on` stays null until someone
  checks the official page; the planner shows that.
- `plan.json` - each program in one bucket:
  - `file_now`: nothing in the row conflicts with the profile.
  - `ask_first`: a requirement is unknown (row or profile), or it may be referral-only.
  - `blocked`: a known requirement is unmet; `blocked_by` names what would unlock it.
  The planner also counts which single unlock (domain, entity, accelerator) opens the most programs.

## Filing rules (enforced by the agent, not this script)
- No payment method, paid plan or purchase without explicit approval per program.
- One account per provider. No multi-accounting.
- Passwords are generated and stored by Proton Pass in a vault the agent alone can see,
  via `signup-broker`; the agent never sees values. Email/phone verification and
  CAPTCHAs go to the human.
