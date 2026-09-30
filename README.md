# CRISPR Base Editor Window Agent

### [Open the Live Application →](https://abusuraihsakhri.github.io/crispr-base-editor-window-agent/)

A research-use Python and browser tool for inspecting fixed activity-window profiles for selected cytosine and adenine base editors. It identifies editable positions within a 20-nt protospacer, distinguishes the intended target from same-locus bystander bases, and reports a deterministic heuristic score for each editable position.

## Scope

Supported editor profiles are `BE4MAX`, `BE3`, `TARGET_AID`, `ABE7.10`, and `ABE8E`. The encoded per-position weights are fixed software heuristics. They are **not experimentally calibrated editing probabilities** and do not model sequence-context effects, chromatin, cell type, delivery, editor expression, PAM compatibility, genome-wide off-target activity, or other experimental determinants.

The `stop_codon_created` flag compares the 20-nt input and edited preview in a simple frame starting at protospacer position 1. It is not a transcript-aware coding consequence predictor.

## Main features

- Validate 20-nt DNA protospacers and 3-symbol IUPAC PAM annotations.
- Evaluate fixed CBE/ABE activity-window weights.
- Select an intended editable position explicitly or automatically choose the highest-weight editable position.
- Identify same-locus bystander bases within the modeled activity window.
- Export deterministic results as JSON or batch CSV.
- Run a FastAPI service for programmatic analysis.
- Run the same Python engine in-browser with Pyodide; guide sequences are processed locally in the browser.

## Installation

Python 3.9 or newer is required.

```bash
python -m pip install -e ".[dev]"
```

## CLI

Evaluate one guide:

```bash
crispr-base-editor-window-agent eval \
  --spacer TTTTCTTTTTTTTTTTTTTT \
  --editor BE4MAX \
  --pos 5
```

JSON output:

```bash
crispr-base-editor-window-agent eval \
  --spacer TTAAAAAAATTTTTTTTTTT \
  --editor ABE8E \
  --json
```

Batch processing:

```bash
crispr-base-editor-window-agent batch -i sample.csv -o results.csv
```

The batch file accepts `spacer` (or `protospacer`/`sequence`), optional `pam`, optional `editor`, and optional `pos` columns.

## REST API

Start the local API:

```bash
uvicorn api:app --host 127.0.0.1 --port 8000
```

Endpoints:

- `GET /health`
- `GET /api/profiles`
- `POST /api/analyze`

Example payload is provided in `sample_payload.json`.

## Browser application

The static app in `web/` loads Pyodide and executes `crispr_base_editor.py` in the browser. It has no project backend and does not transmit guide sequences to this repository. Loading Pyodide itself requires access to the configured CDN.

GitHub Pages deployment is automated from `master` by `.github/workflows/pages.yml`. The deployment workflow also loads the live site in a headless browser, waits for the Pyodide engine, runs a guide analysis, and verifies JSON download output.

## Testing and quality checks

```bash
pytest -q
ruff check --select E9,F63,F7,F82 .
pip-audit .
```

CI validates Python 3.9 through 3.13, package installation, compilation, static checks, tests, an installed-CLI smoke test, dependency auditing, and static browser-app assets.

## Docker

```bash
docker build -t crispr-base-editor-window-agent .
docker run --rm -p 8000:8000 crispr-base-editor-window-agent
```

Or:

```bash
docker compose up --build
```

## Repository structure

- `crispr_base_editor.py` — primary scientific heuristic and CLI.
- `api.py` — FastAPI wrapper around the primary engine.
- `web/` — browser-local Pyodide interface.
- `test_crispr_base_editor.py`, `tests/` — regression and compatibility tests.
- `agents/`, `base_editor_agent/`, `cli.py`, `enrichment.py` — retained legacy compatibility modules; they are not the primary production interface.

## Scientific interpretation

The implementation is a deterministic educational/research utility based on fixed positional windows inspired by early CBE/ABE literature, including Komor et al. (2016), Gaudelli et al. (2017), and later evolved ABE work. The numeric weights in this repository are software assumptions rather than a validated model derived from those publications. Experimental design decisions should use editor- and context-appropriate validated data and tools.

## Privacy

The CLI and local API process inputs on the machine where they run. The GitHub Pages application evaluates sequences in the browser. No analytics or project-side sequence collection is implemented.

## License

MIT. See `LICENSE`.
