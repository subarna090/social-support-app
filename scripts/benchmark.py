"""Benchmark the 004 pipeline on a synthetic run: real extraction/OCR/rules, fake LLM, in-memory DB.

Usage: uv run python scripts/benchmark.py data/synthetic/<run-id> [max-packs]

Ground truth per pack = decision_v1 applied to the answer key's true facts, plus a review finding
when the pack carries a recorded inconsistency. Compares outcome, extracted values and checks.
"""

import json
import sys
import tempfile
import time
from collections import Counter
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
from fastapi.testclient import TestClient  # noqa: E402

from social_support.api.main import create_app  # noqa: E402
from social_support.assessment.document_rules import DocumentRuleAssessor  # noqa: E402
from social_support.config import Settings  # noqa: E402
from social_support.domain.documents import Finding  # noqa: E402
from social_support.domain.models import EmploymentStatus, Outcome  # noqa: E402
from social_support.labelling import HouseholdFacts  # noqa: E402
from tests.conftest import FakeAdvisor  # noqa: E402
from tests.fixtures.demo_upload import upload_pack  # noqa: E402

run = Path(sys.argv[1])
limit = int(sys.argv[2]) if len(sys.argv) > 2 else 10_000
packs = sorted((run / "packs").iterdir())[:limit] if (run / "packs").exists() else [run]

assessor = DocumentRuleAssessor()
MISMATCH = Finding("crosscheck:income_vs_bank", Outcome.NEEDS_HUMAN_REVIEW, "x", ())

FIELD_MAP = {  # (document_type, field) -> answer-key fact
    ("BANK_STATEMENT", "monthly_income_aed"): "net_monthly_income_aed",
    ("ASSETS_LIABILITIES", "total_assets_aed"): "total_assets_aed",
    ("ASSETS_LIABILITIES", "total_liabilities_aed"): "total_liabilities_aed",
    ("CREDIT_REPORT", "credit_score"): "credit_score",
    ("CREDIT_REPORT", "active_credit_defaults"): "active_credit_defaults",
    ("RESUME", "months_employed_last_24"): "months_employed_last_24",
}


def truth(key: dict) -> Outcome:
    f = key["facts"]
    facts = HouseholdFacts.build(
        family_size=f["family_size"],
        net_monthly_income_aed=Decimal(f["net_monthly_income_aed"]),
        employment_status=EmploymentStatus(f["employment_status"]),
        months_employed_last_24=f["months_employed_last_24"],
        total_assets_aed=Decimal(f["total_assets_aed"]),
        total_liabilities_aed=Decimal(f["total_liabilities_aed"]),
        credit_score=f["credit_score"],
        active_credit_defaults=f["active_credit_defaults"],
    )
    findings = (MISMATCH,) if key.get("inconsistency") else ()
    return assessor.assess_case(facts, findings).result.outcome


def same(a, b) -> bool:
    try:
        return Decimal(str(a)) == Decimal(str(b))
    except Exception:
        return str(a) == str(b)


with tempfile.TemporaryDirectory() as tmp:
    settings = Settings(
        _env_file=None, database_url="sqlite://", caseworker_passcode="x", upload_dir=Path(tmp)
    )
    client = TestClient(create_app(settings, advisor=FakeAdvisor()))
    with client:
        rows, times = [], []
        fields_ok = Counter()
        fields_n = Counter()
        checks = Counter()
        for pack in packs:
            key = json.loads((pack / "answer_key.json").read_text(encoding="utf-8"))
            started = time.perf_counter()
            resp = upload_pack(client, pack)
            times.append(time.perf_counter() - started)
            body = resp.json()
            got = body["decision"]["outcome"]
            want = truth(key).value
            docs = {d["document_type"]: d for d in body["documents"]}
            for (dtype, field), fact in FIELD_MAP.items():
                fields_n[dtype + "." + field] += 1
                value = docs.get(dtype, {}).get("fields", {}).get(field)
                if value is not None and same(value, key["facts"][fact]):
                    fields_ok[dtype + "." + field] += 1
            for c in body["cross_checks"]:
                checks[(c["check_id"], c["passed"], bool(key.get("inconsistency")))] += 1
            unreadable = [d for d, v in docs.items() if not v["ok"]]
            rows.append((pack.name, want, got, bool(key.get("inconsistency")), unreadable))
            print(f"{pack.name}: want={want} got={got} {times[-1]:.1f}s", flush=True)

n = len(rows)
agree = sum(w == g for _, w, g, _, _ in rows)
print("\n==== RESULTS ====")
print(f"packs: {n}")
print(f"outcome agreement: {agree}/{n} = {100 * agree / n:.1f}%")
print("truth mix:", Counter(w for _, w, _, _, _ in rows))
print("system mix:", Counter(g for _, _, g, _, _ in rows))
conf = Counter((w, g) for _, w, g, _, _ in rows)
print("confusion (truth, system):", dict(conf))
print("disagreements:", [r for r in rows if r[1] != r[2]])
print("unreadable docs:", [(r[0], r[4]) for r in rows if r[4]])
total_ok, total_n = sum(fields_ok.values()), sum(fields_n.values())
print(f"field accuracy: {total_ok}/{total_n} = {100 * total_ok / total_n:.1f}%")
for k in fields_n:
    print(f"  {k}: {fields_ok[k]}/{fields_n[k]}")
print("cross-checks (check, passed, pack_has_inconsistency): count")
for k, v in sorted(checks.items(), key=str):
    print("  ", k, v)
times.sort()
print(
    f"time per case: mean {sum(times) / n:.1f}s, median {times[n // 2]:.1f}s, "
    f"p95 {times[int(n * 0.95) - 1]:.1f}s, max {times[-1]:.1f}s, total {sum(times) / 60:.1f} min"
)
