# Crispr Base Editor Window Agent

> **Domain:** Computational Biology & AI Drug Discovery  
> **Reference Guidelines & Standards:** `wwPDB, IUPAC & CLSI Computational Guidelines`

<div align="center">

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
![Python](https://img.shields.io/badge/Python-3.10%20%7C%203.11%20%7C%203.12-3776AB.svg?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-009688.svg?logo=fastapi&logoColor=white)
![Audit Trail](https://img.shields.io/badge/Audit-HMAC--SHA256_Tamper--Evident-brightgreen.svg)
![Zero-PHI Guard](https://img.shields.io/badge/Guard-Zero--PHI_Outbound-blue.svg)
![Docker](https://img.shields.io/badge/Docker-Ready-2496ED.svg?logo=docker&logoColor=white)

</div>

---

## 📖 What It Does

CRISPR Base Editor Deamination Window & Bystander Mutation Prediction Engine
-----------------------------------------------------------------------------
Simulates Cytosine Base Editors (CBE: BE3, BE4max, Target-AID) and Adenine Base Editors
(ABE: ABE7.10, ABE8e, ABE9) activity windows, calculates position-dependent deamination
efficiencies, predicts bystander edit probabilities, and models codon alteration consequences.

Domain: Synthetic Biology / Genome Engineering / Molecular Therapeutics
Reference: Komor et al. Nature 2016; Gaudelli et al. Nature 2017; Richter et al. Nat Biotech 2020

---

## ⚙️ Key Capabilities & Algorithmic Modules

### 🔬 Core Algorithmic & Evaluation Engines

- **`TargetBaseEditDetail`**: Individual editable base within protospacer.
- **`BaseEditorAnalysisResult`**: Complete CRISPR base editor protospacer evaluation.
- **`CRISPRBaseEditorEngine`**: Engine for simulating base editor deamination windows and bystander edits.

---

## 💻 CLI Quickstart & Usage

### CRISPR Base Editor Engine (`crispr_base_editor.py`)

#### Evaluate a Single Protospacer
```bash
python crispr_base_editor.py eval --spacer ATCGATCGATCGATCGATCGAT --editor BE4MAX --pos 5
```

#### JSON Output
```bash
python crispr_base_editor.py eval --spacer ATCGATCGATCGATCGATCGAT --editor ABE8E --json
```

#### Batch Process gRNA CSV
```bash
python crispr_base_editor.py batch -i sample.csv -o results.csv
```

#### Ask Base Editing Questions
```bash
python crispr_base_editor.py chat "What is the editing window?"
```

### Enterprise Agent CLI (`cli.py`)

#### Run Single Task Evaluation
```bash
python cli.py audit --task-id TASK-001 --target TARGET-01 --primary 28.5 --secondary 14.2 --critical --status DISCORDANT
```

#### Batch Process Task Records
```bash
python cli.py batch -i sample.csv -o results.csv
```

#### Verify Audit Trail Integrity
```bash
python cli.py verify-audit
```

#### Launch FastAPI REST Server
```bash
python cli.py serve --host 127.0.0.1 --port 8000
```

### Input Data Schema (Batch CSV)

| Field | Description | Requirement |
|:------|:------------|:------------|
| `task_id` | Unique task identifier | Required |
| `target_identifier` | Target entity identifier | Required |
| `primary_metric` | Primary measurement value | Required |
| `secondary_metric` | Secondary measurement value | Required |
| `is_critical_flag` | Critical escalation flag | Optional |
| `status_descriptor` | Status code descriptor | Optional |

---

## 🛡️ Security & Enterprise Architecture

* **Zero-PHI Outbound Interceptor:** Active regex inspection blocking SSNs, MRNs, phone numbers, emails, and patient identifiers.
* **Tamper-Evident HMAC-SHA256 Audit Trail:** Chained, cryptographically signed logs for every evaluation and state transition. Set `AUDIT_SECRET_KEY` environment variable for persistent audit integrity across restarts.
* **Air-Gapped LLM Reasoning Adapter:** Agnostic integration for local Ollama instances (`llama3`, `mistral`), Claude 3.5 Sonnet, GPT-4o, and deterministic test mocks.
* **Active Learning Bayesian Calibration:** Dynamic tracker updating worker reliability weights and monitoring Brier calibration drift.
* **FastAPI & Prometheus Telemetry:** Exposes OpenAPI 3.1 REST endpoints and operational Prometheus metrics (`/metrics`).
* **Path Traversal Protection:** Input validation prevents directory traversal attacks in batch processing.
* **Secure Error Handling:** API endpoints return generic error messages to prevent information leakage.

### Environment Variables

| Variable | Description | Default |
|:---------|:------------|:--------|
| `AUDIT_SECRET_KEY` | Secret key for HMAC-SHA256 audit trail signing | Randomly generated (ephemeral) |

---

## 🧪 Testing & Verification

### Install Development Dependencies
```bash
pip install -e ".[dev]"
```

### Run the Automated Test Suite
```bash
pytest -v
```

Tests cover:
- CBE & ABE editor type mapping and window profiles
- Protospacer evaluation and bystander mutation prediction
- Stop codon detection and JSON export
- CLI command execution
- **Security features**: PHI detection, HMAC audit trail integrity, tamper detection, path traversal prevention

### Execute High-Throughput Simulation
```bash
python simulator.py 1000
```

---

## 🐳 Container Deployment

```bash
docker build -t crispr-base-editor-window-agent .
docker run -p 8000:8000 crispr-base-editor-window-agent
```
