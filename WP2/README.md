# Open Healthcare Dataset Explorer

A tool to browse metadata and data quality results for open healthcare datasets (currently NHANES), enriched using an LLM.

---

## What this does

- Browse a catalog of healthcare datasets with searchable, filterable metadata (variables, data types, target populations, value codes)
- View OMOP CDM data quality dashboard (DQD) results for datasets that have been loaded into a standardized database

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


## Project structure

### UI files
| File | Purpose |
|------|---------|
| `index.html` | Main page — shows all dataset cards, filterable by data type and ML task. |
| `schema.html` | Dataset detail page — shows all variables with labels, English text, target population, value codes, counts, data type, unit, and analyst notes. |
| `app.js` | Logic for `index.html` — handles filtering, rendering dataset cards, and navigating to the schema page. |
| `style.css` | Shared styles used across all pages. |
| `api.py` | Serves the static UI and provides the `/api/dqd/result` endpoint that reads DQD results from `dqd/raw/`. |

### Data files (do not edit manually)
| File | Purpose |
|------|---------|
| `schema.json` | Stores all extracted metadata for every dataset. Read by `schema.html` to display variable tables. |
| `data.js` | Stores the dataset list (name, description, subtypes, tasks, source, last updated, doc URL) used to render cards in `index.html`. |
| `dqd/raw/` | DQD check results (JSON), one file per dataset. |
| `dqd/mapping/` | OMOP CDM variable mappings, one file per dataset. |
| `dqd/results/` | DQD run logs. |

---

## Want to add or reproduce data yourself?

- **Extract metadata for a new dataset** → see [EXTRACTION.md](EXTRACTION.md)
- **Run DQD checks on a new dataset** (requires R, PostgreSQL, OMOP CDM) → see [DQD.md](DQD.md)
