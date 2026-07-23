# TVTimeCompare

TVTimeCompare validates a migration from a TV Time GDPR export to a Refract
export. It identifies TV Time watched episodes missing from Refract and records
any source rows omitted during parsing.

## Requirements

- Python 3.12 or later

## Installation

For local development:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
```

## Usage

```bash
tvtimecompare compare tvtime.zip refract.zip
```

The command reads both ZIP archives, compares watched episodes, writes CSV and
HTML reports to `reports/`, and prints comparison and import diagnostics. Use
`--output-dir` to choose another report directory.

Reader functions return an export result containing both the parsed `shows` and
per-file diagnostics (`rows_read`, `rows_imported`, skipped-row counts, and
skip reasons).

## Development

```bash
pytest
ruff check .
black --check .
```

## License

Distributed under the [MIT License](LICENSE).
