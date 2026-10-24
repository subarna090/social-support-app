"""Seed the running application with a generated run (FR-019, FR-020, research R11).

Packs go through the application's normal submission endpoint via the UI's HTTP client, so the
generator never touches the application's internals. Only pack ids, reference numbers and counts
are logged or printed; never names, Emirates IDs or incomes.
"""

import csv
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

from social_support.services.tracing import LOGGER_NAME
from social_support.synthetic.run import RequestError
from social_support.ui.client import ApiClient, ApiError

logger = logging.getLogger(f"{LOGGER_NAME}.synthetic")

REPORT_COLUMNS = [
    "pack_id",
    "status",
    "reference_number",
    "returned_outcome",
    "eligibility_outcome",
    "matched",
]


@dataclass
class SeedingSummary:
    total: int
    report_path: Path
    submitted: int = 0
    rejected: int = 0
    matched: int = 0
    unreachable: bool = False
    references: dict[str, str] = field(default_factory=dict)  # pack id -> reference number


def seed_run(run_folder: Path, client: ApiClient, limit: int | None = None) -> SeedingSummary:
    run_folder = Path(run_folder)
    if not (run_folder / "run.json").is_file():
        raise RequestError(f"not a generated run: {run_folder}")
    packs = sorted((run_folder / "packs").iterdir())[:limit]
    summary = SeedingSummary(total=len(packs), report_path=run_folder / "seeding_report.csv")
    rows: list[dict] = []
    for pack in packs:
        form = json.loads((pack / "form.json").read_text(encoding="utf-8"))
        key = json.loads((pack / "answer_key.json").read_text(encoding="utf-8"))
        expected = key["eligibility"]["outcome"]
        try:
            result = client.submit(form["submission"])
        except ApiError as exc:
            if exc.status_code == 0:  # unreachable: stop, and report only what was submitted
                summary.unreachable = True
                logger.info("application unreachable", extra={"pack_id": pack.name})
                break
            summary.rejected += 1
            rows.append(
                {"pack_id": pack.name, "status": "rejected", "eligibility_outcome": expected}
            )
            logger.debug("pack rejected", extra={"pack_id": pack.name, "status": "rejected"})
            continue
        returned = result["decision"]["outcome"]
        matched = returned == expected
        summary.submitted += 1
        summary.matched += matched
        summary.references[pack.name] = result["reference_number"]
        rows.append(
            {
                "pack_id": pack.name,
                "status": "submitted",
                "reference_number": result["reference_number"],
                "returned_outcome": returned,
                "eligibility_outcome": expected,
                "matched": str(matched).lower(),
            }
        )
        logger.debug(
            "pack seeded",
            extra={"pack_id": pack.name, "reference_number": result["reference_number"]},
        )
    with summary.report_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_COLUMNS, restval="", lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    return summary
