# TVTimeCompare

TVTimeCompare validates a migration from a TV Time GDPR export to a Refract
export. It identifies TV Time watched episodes missing from Refract and records
any source rows omitted during parsing.

Exact normalized titles are matched before conservative RapidFuzz title matching.
Fuzzy matches need a configurable confidence score and an unambiguous lead over
the next candidate; uncertain matches are reported separately for review.

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

## Desktop application

Install the optional Qt interface and launch it with either command:

```bash
python -m pip install -e ".[gui]"
tvtimecompare-gui
# or: tvtimecompare gui
```

The desktop interface uses the same readers, comparison engine, and report
generator as the CLI. It keeps work off the interface thread, shows import and
comparison progress, summarizes the result, and can open the generated HTML
report or report folder.

## Development

```bash
pytest
ruff check .
black --check .
```

## License

Distributed under the [MIT License](LICENSE).
