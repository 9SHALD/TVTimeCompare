# TVTimeCompare

TVTimeCompare helps you validate a migration from a TV Time GDPR export to a
Refract export. It will ultimately identify watched episodes present in TV Time
but missing from Refract, including fuzzy matching for differently formatted
show titles.

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

The `compare` command currently validates the input files and provides the
command interface. Export parsing, matching, and report generation will follow
in subsequent releases.

## Development

```bash
pytest
ruff check .
black --check .
```

## License

Distributed under the [MIT License](LICENSE).
