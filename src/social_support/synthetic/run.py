"""Generation runs: validate the request, then write a complete run folder (research R9).

Nothing is written unless the request is valid. Packs are written into a temporary sibling folder
that is renamed into place at the end, so an interrupted run never leaves a half-written folder.
"""

import hashlib
import json
import logging
import random
import shutil
import time
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path

from social_support.domain.models import Outcome
from social_support.labelling import LabellingPolicy, load_policy
from social_support.services.tracing import LOGGER_NAME
from social_support.synthetic import GENERATOR_VERSION
from social_support.synthetic.allocation import assign_targets, quotas
from social_support.synthetic.dataset import summary_row, write_summary
from social_support.synthetic.inconsistencies import InconsistencyType, inject, select_slots
from social_support.synthetic.pack import FORMAT, build_pack, write_pack
from social_support.synthetic.profile import pack_rng, sample_profile

logger = logging.getLogger(f"{LOGGER_NAME}.synthetic")

MAX_COUNT = 5000
DEFAULT_AS_OF = date(2026, 10, 1)
INCONSISTENCY_TYPES = {  # CLI name -> type (research R8)
    "income": "INCOME_MISMATCH",
    "address": "ADDRESS_MISMATCH",
    "family_size": "FAMILY_SIZE_MISMATCH",
    "identity": "IDENTITY_MISMATCH",
    "employment": "EMPLOYMENT_MISMATCH",
}


class RequestError(ValueError):
    """An invalid request. The message is shown to the user as-is (contracts/cli.md)."""


@dataclass(frozen=True)
class GenerationRequest:
    count: int
    seed: int
    inconsistency_rate_pct: int = 0
    inconsistency_types: tuple[str, ...] = tuple(INCONSISTENCY_TYPES.values())
    outcome_mix_pct: dict[str, int] | None = None
    as_of: date = DEFAULT_AS_OF
    output_root: Path = Path("data/synthetic")
    overwrite: bool = False

    def validate(self) -> None:
        if not 1 <= self.count <= MAX_COUNT:
            raise RequestError(f"count must be between 1 and {MAX_COUNT}")
        if self.seed < 0:
            raise RequestError("seed must be zero or a positive integer")
        if not 0 <= self.inconsistency_rate_pct <= 100:
            raise RequestError("inconsistency rate must be between 0 and 100")
        if not self.inconsistency_types or not set(self.inconsistency_types) <= set(
            INCONSISTENCY_TYPES.values()
        ):
            raise RequestError("unknown inconsistency type")
        mix = self.outcome_mix_pct
        if mix is not None and (
            set(mix) != {o.value for o in Outcome}
            or any(not 0 <= v <= 100 for v in mix.values())
            or sum(mix.values()) != 100
        ):
            raise RequestError("outcome mix must be three percentages that add up to 100")

    def settings(self) -> dict:
        return {
            "count": self.count,
            "seed": self.seed,
            "inconsistency_rate_pct": self.inconsistency_rate_pct,
            "inconsistency_types": sorted(self.inconsistency_types),
            "outcome_mix_pct": self.outcome_mix_pct,
            "as_of": self.as_of.isoformat(),
        }

    @property
    def run_id(self) -> str:
        canonical = json.dumps(self.settings(), sort_keys=True)
        digest = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:6]
        return f"s{self.seed}-n{self.count}-{digest}"

    @property
    def folder(self) -> Path:
        return Path(self.output_root) / self.run_id


@dataclass(frozen=True)
class GenerationRun:
    run_id: str
    folder: Path
    policy_version_id: str
    counts: dict = field(default_factory=dict)


def check(request: GenerationRequest) -> None:
    """Every check that must pass before anything is written."""
    request.validate()
    if request.folder.exists() and not request.overwrite:
        raise RequestError(
            f"output already exists: {request.folder} (use --overwrite to replace it)"
        )


def _rename_with_retry(source: Path, target: Path, attempts: int = 20) -> None:
    """On Windows a virus scanner or indexer can briefly hold files that were just written, so a
    folder rename fails with "Access is denied". Retry for up to about 5 seconds."""
    for attempt in range(attempts):
        try:
            source.rename(target)
            return
        except PermissionError:
            if attempt == attempts - 1:
                raise
            time.sleep(0.25)


def generate(request: GenerationRequest, policy: LabellingPolicy | None = None) -> GenerationRun:
    check(request)
    policy = policy or load_policy()
    run_id, final = request.run_id, request.folder
    temp = final.with_name(f".{run_id}.partial")
    if temp.exists():
        shutil.rmtree(temp)
    # Run-level decisions use their own generator, so packs stay independent of each other (R5).
    master = random.Random(request.seed)
    slots = (
        select_slots(
            master, request.count, request.inconsistency_rate_pct, request.inconsistency_types
        )
        if request.inconsistency_rate_pct
        else {}
    )
    targets = (
        assign_targets(master, quotas(request.count, request.outcome_mix_pct))
        if request.outcome_mix_pct
        else [None] * request.count
    )
    try:
        eligibility: Counter[str] = Counter()
        routing: Counter[str] = Counter()
        injected: Counter[str] = Counter()
        rows: list[dict] = []
        for index in range(1, request.count + 1):
            rng = pack_rng(request.seed, index)
            kind = slots.get(index)
            profile = sample_profile(
                rng,
                request.as_of,
                pack_index=index,
                target=targets[index - 1],
                policy=policy,
                requires_income=kind is InconsistencyType.INCOME_MISMATCH,
                requires_employment=kind is InconsistencyType.EMPLOYMENT_MISMATCH,
            )
            pack = build_pack(index, profile, policy, request.as_of, rng)
            if kind:
                inject(pack, kind, rng)
                injected[kind.value] += 1
            write_pack(pack, temp / "packs" / pack.pack_id, run_id, request.as_of, rng)
            eligibility[pack.label.outcome.value] += 1
            routing[pack.expected_routing.value] += 1
            rows.append(summary_row(pack))
            logger.info("pack generated", extra={"run_id": run_id, "pack_id": pack.pack_id})

        counts = {
            "packs": request.count,
            "eligibility": {o.value: eligibility[o.value] for o in Outcome},
            "expected_routing": {o.value: routing[o.value] for o in Outcome},
            "inconsistencies": {
                t.value: injected[t.value] for t in InconsistencyType if injected[t.value]
            },
        }
        record = {
            "format": FORMAT,
            "run_id": run_id,
            "request": request.settings(),
            "generator_version": GENERATOR_VERSION,
            "policy_version_id": policy.version_id,
            "generated_at": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "counts": counts,
        }
        write_summary(temp, rows)
        (temp / "run.json").write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
        )
        if final.exists():
            shutil.rmtree(final)
        _rename_with_retry(temp, final)
    except BaseException:
        shutil.rmtree(temp, ignore_errors=True)
        raise
    logger.info("run complete", extra={"run_id": run_id, "status": "ok"})
    return GenerationRun(run_id, final, policy.version_id, counts)
