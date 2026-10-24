"""T016: the ``generate`` command against contracts/cli.md."""

import json

import pytest

from social_support.synthetic.cli import main


def run_cli(capsys, *args):
    code = main(list(args))
    out, err = capsys.readouterr()
    return code, out, err


def test_generate_prints_a_summary_without_personal_data(tmp_path, capsys):
    code, out, err = run_cli(
        capsys, "generate", "--count", "3", "--seed", "4", "--out", str(tmp_path)
    )
    assert code == 0, err
    lines = out.strip().splitlines()
    assert lines[0].startswith("Generated 3 packs in ")
    assert lines[1].startswith("Eligibility: APPROVE ")
    assert lines[2].startswith("Inconsistencies: 0")
    assert lines[3].startswith("Policy: eligibility/v1+")
    (run_folder,) = tmp_path.iterdir()
    for pack in (run_folder / "packs").iterdir():
        form = json.loads((pack / "form.json").read_text(encoding="utf-8"))
        for secret in (form["full_name"], form["emirates_id"], form["net_monthly_income_aed"]):
            assert secret not in out


@pytest.mark.parametrize(
    ("args", "message"),
    [
        (["--count", "0"], "count must be between 1 and 5000"),
        (["--count", "5001"], "count must be between 1 and 5000"),
        (["--seed", "-1"], "seed must be zero or a positive integer"),
        (["--inconsistency-rate", "101"], "inconsistency rate must be between 0 and 100"),
        (
            ["--inconsistency-types", "income,salary"],
            "unknown inconsistency type: salary (expected: income, address, family_size, "
            "identity, employment)",
        ),
        (["--outcome-mix", "50,30,10"], "outcome mix must be three percentages that add up to 100"),
        (["--outcome-mix", "50,50"], "outcome mix must be three percentages that add up to 100"),
    ],
)
def test_invalid_arguments_exit_2_and_write_nothing(tmp_path, capsys, args, message):
    base = {"--count": "3", "--seed": "1"}
    for flag, value in zip(args[::2], args[1::2], strict=True):
        base[flag] = value
    argv = ["generate", "--out", str(tmp_path)] + [x for kv in base.items() for x in kv]
    code, _, err = run_cli(capsys, *argv)
    assert code == 2
    assert err.strip().endswith(message)
    assert list(tmp_path.iterdir()) == []


def test_existing_run_is_not_overwritten_without_flag(tmp_path, capsys):
    argv = ["generate", "--count", "2", "--seed", "8", "--out", str(tmp_path)]
    assert run_cli(capsys, *argv)[0] == 0
    (run_folder,) = tmp_path.iterdir()
    marker = run_folder / "keep.txt"
    marker.write_text("old", encoding="utf-8")

    code, _, err = run_cli(capsys, *argv)
    assert code == 2
    assert f"output already exists: {run_folder} (use --overwrite to replace it)" in err
    assert marker.exists()

    assert run_cli(capsys, *argv, "--overwrite")[0] == 0
    assert not marker.exists()
    assert len(list((run_folder / "packs").iterdir())) == 2
    assert [p.name for p in tmp_path.iterdir()] == [run_folder.name]  # no temp folders left


def test_final_rename_retries_when_windows_holds_the_folder(tmp_path, monkeypatch):
    # A scanner holding just-written files makes the rename fail briefly with "Access is denied".
    from pathlib import Path

    from social_support.synthetic import run as run_module

    real_rename, calls = Path.rename, []

    def flaky_rename(self, target):
        calls.append(self)
        if len(calls) < 3:
            raise PermissionError(5, "Access is denied")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", flaky_rename)
    monkeypatch.setattr(run_module.time, "sleep", lambda _: None)
    result = run_module.generate(
        run_module.GenerationRequest(count=1, seed=3, output_root=tmp_path)
    )
    assert result.folder.is_dir() and len(calls) == 3


def test_cli_runs_emit_structured_logs_without_personal_data(tmp_path, capsys):  # T047
    code = main(["generate", "--count", "2", "--seed", "6", "--out", str(tmp_path)])
    _, err = capsys.readouterr()
    assert code == 0
    records = [json.loads(line) for line in err.splitlines() if line.startswith("{")]
    complete = [r for r in records if r["message"] == "run complete"]
    assert len(complete) == 1 and complete[0]["run_id"].startswith("s6-n2-")
    assert not [r for r in records if r["message"] == "pack generated"]  # per-pack is DEBUG
    (run_folder,) = tmp_path.iterdir()
    for pack in (run_folder / "packs").iterdir():
        form = json.loads((pack / "form.json").read_text(encoding="utf-8"))
        for secret in (form["full_name"], form["emirates_id"], form["net_monthly_income_aed"]):
            assert secret not in err
