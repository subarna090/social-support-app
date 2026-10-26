# CLI Contract addition (004)

```text
social-support-data demo [--out data/demo] [--force]
```

- Writes `<out>/approve/`, `<out>/soft_decline/` and `<out>/review/`, each holding
  `bank_statement.pdf`, `emirates_id.png`, `resume.pdf`, `assets_liabilities.xlsx`,
  `credit_report.pdf`, `form.json` (the values to type into the form) and `answer_key.json`
  (pack-format/1, including `expected_routing`).
- Deterministic: the same output bytes on every run (fixed profiles, as-of 2026-10-01, invariant PDFs).
- If `<out>` already has packs: exits with code 2 and a message, unless `--force` is given, which
  replaces only those three folders.
- Prints one line per pack: folder, expected outcome, and the form values to enter.
