# Open Healthcare Dataset Explorer — User Guide

Browse metadata and OMOP CDM data quality results for open healthcare datasets (currently NHANES and PHIDU), enriched using an LLM.

This guide is for **using** the tool — browsing datasets and viewing their data quality reports. If you want to add new datasets or regenerate quality checks yourself, see:

- **Add a new dataset's metadata** → [EXTRACTION.md](EXTRACTION.md)
- **Run/regenerate data quality checks** → [DQD.md](DQD.md)
- **What's currently in the tool** → [DATASETS.md](DATASETS.md)

---

## What this does

- Browse a catalog of healthcare datasets with searchable, filterable metadata (variables, data types, target populations, value codes)
- View OMOP CDM Data Quality Dashboard (DQD) results for datasets that have been loaded into a standardized database — each dataset's report is isolated to just its own data, not mixed in with every other dataset

---

## Quick Start

### Step 1 — Clone the repository

```bash
git clone https://github.com/jennyVVei/open-healthcare-dataset-explorer-quality-tool.git
cd open-healthcare-dataset-explorer-quality-tool
```

### Step 2 — Set Up Environment & Install Dependencies

Ensure you have Python 3.9+ installed. Choose the setup method that matches your environment:

#### Option A: Standard Python (venv)
##### On macOS / Linux:
```Bash
# Create virtual environment
python3 -m venv venv

# Activate virtual environment
source venv/bin/activate

# Install dependencies
pip install flask flask-cors pandas psycopg2-binary pyreadstat openpyxl
```

##### On Windows:
```PowerShell
# Create virtual environment
python -m venv venv

# Activate virtual environment
# In PowerShell:
.\venv\Scripts\Activate.ps1
# Or in Command Prompt (cmd):
.\venv\Scripts\activate.bat

# Install dependencies
pip install flask flask-cors pandas psycopg2-binary pyreadstat openpyxl
```

*Note for Windows PowerShell users: If script execution is restricted, run `Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned` in your terminal before activating.*

#### Option B: Conda Environment (Cross-Platform)
```Bash
# Create and activate environment with Python 3.9+
conda create -n app-env python=3.10 -y
conda activate app-env

# Install dependencies
pip install flask flask-cors pandas psycopg2-binary pyreadstat openpyxl
```

### Step 3 — Start the server

Make sure your environment is activated before running the application:

#### macOS / Linux (venv):

```Bash
source venv/bin/activate && python3 api.py
```

#### Windows (venv):

```PowerShell
# PowerShell
.\venv\Scripts\Activate.ps1; python api.py

# Command Prompt (cmd)
.\venv\Scripts\activate.bat && python api.py
```

#### Conda (All platforms):

```Bash
conda activate app-env
python api.py
```

*Keep this terminal window open while using the tool.*


### Step 4 — Open the UI

Open your browser and go to:

```
http://localhost:8765
```

Browse dataset cards, click into a dataset to see its full variable schema, or view its DQD results if available.

---

## What you'll see when browsing

Most datasets have a **View DQD** button that opens an isolated quality report scoped just to that dataset — denominators, pass/fail rates, and flagged issues all reflect that dataset alone, not the whole database.

A small number of datasets show a **"DQD not applicable"** message instead of a report. This isn't a bug or a missing report — it means the dataset genuinely doesn't fit the OMOP CDM structure that DQD checks against. Two kinds of datasets fall into this category:

- **Reference/lookup tables** (e.g. NHANES food code lists, supplement ingredient lists) — these have no participant identifier linking rows to individual people, so they're loaded into the CDM's vocabulary (`concept`) table instead.
- **PHIDU regional statistics** — these report population-level rates and counts for a state or health area, not individual-person records, so they aren't loaded into the OMOP CDM at all.

See [DATASETS.md](DATASETS.md) for the current, complete breakdown of what's been processed and what each dataset's status is.

---

## Project structure

### UI files
| File | Purpose |
|------|---------|
| `index.html` | Main page — shows all dataset cards, filterable by data type and ML task. |
| `schema.html` | Dataset detail page — shows all variables with labels, English text, target population, value codes, counts, data type, unit, and analyst notes; also the "View DQD" button and report display. |
| `app.js` | Logic for `index.html` — handles filtering, rendering dataset cards, and navigating to the schema page. |
| `style.css` | Shared styles used across all pages. |
| `api.py` | Serves the static UI and provides `/api/schema/<id>`, `/api/dqd/result`, and `/api/phidu/data/<id>` endpoints, reading from `schema.json` and `dqd/raw/`. |

### Data files (do not edit manually)
| File | Purpose |
|------|---------|
| `schema.json` | Stores all extracted metadata for every dataset. Read by `schema.html` to display variable tables. |
| `data.js` | Stores the dataset list (name, description, subtypes, tasks, source, last updated, doc URL) used to render cards in `index.html`. |
| `dqd/raw/` | Isolated DQD check results (JSON), one file per dataset. |
| `dqd/mapping/` | OMOP CDM variable mappings, one file per dataset. |
| `dqd/results/` | DQD run logs. |
| `dqd/concept_specs/` | Mapping specs for reference/lookup datasets loaded into the CDM's `concept` table instead of person-level tables. |

---

## Want to add or reproduce data yourself?

- **Extract metadata for a new dataset** → see [EXTRACTION.md](EXTRACTION.md)
- **Run isolated DQD checks on a new dataset** (requires R, PostgreSQL, OMOP CDM) → see [DQD.md](DQD.md)
- **Check current dataset coverage** → see [DATASETS.md](DATASETS.md)
