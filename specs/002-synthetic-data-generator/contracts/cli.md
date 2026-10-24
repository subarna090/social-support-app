# CLI Contract: `social-support-data`

A console script registered in `pyproject.toml`. It can also be run as
`uv run python -m social_support.synthetic`. Exit codes: `0` success, `1` runtime failure
(for example the application is unreachable while seeding, or the profile sampler gives up),
`2` invalid arguments. On exit code 2 nothing has been written.

Console output never contains names, Emirates IDs, addresses or incomes; it shows only pack ids,
reference numbers, counts and paths.

---

## `generate`

```text
social-support-data generate --count N --seed S
    [--inconsistency-rate PCT]          # 0–100, default 0
    [--inconsistency-types T[,T...]]    # income,address,family_size,identity,employment; default all
    [--outcome-mix A,D,R]               # Approve,Soft Decline,Needs Human Review percentages, sum 100;
                                        # default: natural distribution
    [--as-of YYYY-MM-DD]                # default 2026-10-01
    [--out DIR]                         # default data/synthetic
    [--overwrite]                       # replace an existing run folder
```

| Argument check | Message (stderr) | Exit |
|---|---|---|
| `--count` outside 1–5000 | `count must be between 1 and 5000` | 2 |
| `--seed` negative | `seed must be zero or a positive integer` | 2 |
| `--inconsistency-rate` outside 0–100 | `inconsistency rate must be between 0 and 100` | 2 |
| unknown inconsistency type | `unknown inconsistency type: <t> (expected: income, address, family_size, identity, employment)` | 2 |
| `--outcome-mix` not three integers 0–100 summing to 100 | `outcome mix must be three percentages that add up to 100` | 2 |
| run folder exists, no `--overwrite` | `output already exists: <path> (use --overwrite to replace it)` | 2 |

On success, stdout ends with a summary:

```text
Generated 100 packs in data/synthetic/s42-n100-3fa2c1
Eligibility: APPROVE 40, SOFT_DECLINE 40, NEEDS_HUMAN_REVIEW 20
Inconsistencies: 30 (INCOME_MISMATCH 12, ADDRESS_MISMATCH 18)
Policy: eligibility/v1+8c1d2e4f
```

## `seed`

```text
social-support-data seed --run DIR
    [--limit N]            # seed only the first N packs (in pack id order)
    [--api-base-url URL]   # default: API_BASE_URL from the environment, then .env, then http://127.0.0.1:8000
```

| Situation | Behaviour | Exit |
|---|---|---|
| `--run` folder missing or has no `run.json` | `not a generated run: <path>` | 2 |
| Application unreachable before or during seeding | `The assessment service can't be reached. Check that the API is running.`, then `Submitted <k> of <n> packs before stopping.` `seeding_report.csv` lists only those `k` | 1 |
| API answers 422 for a pack | that pack's status is `rejected`; continue | 0 |
| All submitted | `Seeded <n> packs: <m> matched the eligibility outcome, <n-m> differed. Report: <path>` | 0 |

Running `seed` twice for the same run submits the applications again. The 001 app accepts them as
new applications and notes that a previous application exists. This is intended.
