# Running the DQD (Data Quality Dashboard)

This guide is for adding new datasets to the DQD pipeline — running the ETL and quality checks yourself, isolated per dataset. If you only want to browse DQD results that are already in this repo, you do not need any of this: just run `python3 api.py` and open the web UI (see main [README](README.md)).

**Pipeline:** `etl_v3.py` (loads a dataset into an OMOP CDM table, registering which rows it owns) → `generate_dataset_view_schema.py` (builds a view scoped to just that dataset's rows) → `dqd.R` (runs the isolated quality checks against that view) → results appear in `dqd/raw/`, `dqd/mapping/`, `dqd/results/`, viewable via `api.py` + the web UI, or directly with `viewDqDashboard()`.

---

## Why isolation, not just "run DQD on the whole database"

`DataQualityDashboard` normally checks against a database's `public` schema as a whole. That's the standard OHDSI use case — assessing an entire CDM instance's quality. But it means every dataset's contribution gets mixed together: a check's denominator reflects *everyone's* rows, not just the one dataset you're trying to evaluate.

This project instead gives every dataset its own isolated view, so its DQD report reflects only its own data. This requires tracking which `ds_id` inserted which row — that's what `dataset_row_registry` does, and it's the foundation everything else in this guide builds on.

---

## Prerequisites checklist

- [ ] R (>= 4.0.0)
- [ ] Java (>= 8)
- [ ] PostgreSQL running locally
- [ ] Python 3.9+ with `pandas`, `psycopg2-binary`, `pyreadstat`
- [ ] A NIM API key (see [EXTRACTION.md](EXTRACTION.md)) — `etl_v3.py` uses this to generate OMOP mappings

---

## 1. Install R and Java

```bash
brew install r
brew install openjdk
java -version   # confirm 8 or higher
```

## 2. Install R packages

```r
install.packages("remotes")
install.packages("DatabaseConnector")
remotes::install_github("OHDSI/DataQualityDashboard")
```

If `DatabaseConnector` fails to load due to `rJava`, confirm Java is installed and reinstall:
```r
install.packages("rJava")
```

## 3. Download the JDBC driver

```r
library(DatabaseConnector)
downloadJdbcDrivers("postgresql", pathToDriver = "jdbc")
```

This populates the `jdbc/` folder (gitignored, machine-specific). Check that `dqd.R`'s `pathToDriver` value points to this folder's **absolute path** on your machine.

## 4. Set up PostgreSQL and create the OMOP CDM schema

```bash
createdb omop
```

```r
install.packages("devtools")
devtools::install_github("OHDSI/CommonDataModel")

cd <- DatabaseConnector::createConnectionDetails(
  dbms = "postgresql",
  server = "localhost/omop",
  port = 5433,
  user = "omop_user",
  password = "omop_pass",
  pathToDriver = "jdbc"
)

CommonDataModel::executeDdl(
  connectionDetails = cd,
  cdmVersion = "5.3",
  cdmDatabaseSchema = "public"
)
```

Adjust `server`, `port`, `user`, `password` to match your actual Postgres setup.

## 5. Set up the isolation registry tables

Run these once against your `omop` database (via `docker cp <file> <container>:/tmp/` then `psql -f`, or however you connect):

```bash
create_dataset_row_registry.sql        # tracks which ds_id owns which row (single owner)
create_shared_row_registry.sql          # tracks rows genuinely shared by multiple datasets (many-to-many)
```

**Do not skip this.** `generate_dataset_view_schema.py` will fail immediately for any dataset with no `dataset_row_registry` entries.

### Add the composite index — do this before running DQD on any real amount of data

```sql
CREATE INDEX idx_dataset_row_registry_ds_id_table_name
    ON dataset_row_registry (ds_id, table_name);
```

Without this index, a single dataset's isolated DQD run can take 30+ minutes once `dataset_row_registry` grows past a few million rows (the isolated view's filter can't use the table's other indexes efficiently). With it, most datasets finish in a few minutes even at tens of millions of registry rows. Build this with `CREATE INDEX CONCURRENTLY` if the table already has data and you don't want to lock it — but run that inside `caffeinate` or equivalent, since an interrupted concurrent build leaves an unusable `INVALID` index that has to be dropped and rebuilt.

## 6. Install Python dependencies

```bash
pip install pandas psycopg2-binary pyreadstat --break-system-packages
```

Also make sure `.env` has a valid NIM API key.

---

## 7. Run the pipeline end to end

**Single dataset, full ETL:**
```bash
python3 etl_v3.py nhanes-demographics-demo_i-2015
python3 batch_etl_dqd_new.py --ids nhanes-demographics-demo_i-2015
```

**Batch, full ETL for a whole category (skips datasets already done):**
```bash
python3 batch_etl_dqd_new.py --category demographics
```

**Batch, skip re-running ETL** (use when the dataset's rows are already correctly loaded and registered — just need the isolated view + DQD regenerated):
```bash
python3 batch_etl_dqd_new.py --category dietary --skip-etl
```

If everything is set up correctly, you should see real-time check progress streamed to your terminal (`Processing check description: ...`), then:
```
[DQD] Done: dqd/raw/nhanes-demographics-demo_i-2015.json
[DQD] Log moved to: dqd/results/log_DqDashboard_...txt
```

---

## Before running a new category: check for backfill vs. full ETL, and shared variables

Don't assume every dataset in a new category needs a full ETL run — some may already have real data loaded (from before this registry existed), just not yet registered. Others may share variable names with sibling datasets in the same survey cycle, which needs special handling. Both are worth checking before a big batch run.

### 1. Classify: does real data already exist, or does this need full ETL?

```bash
python3 classify_backfill_failures.py --category examination --output examination_classification.json
```

This checks, per dataset, whether matching rows already exist in `measurement`/`observation` (via SEQN + variable-name matching) — independent of whether they're registered yet. It buckets each dataset into `ok` (real data exists, just needs registry backfill), `never_etld` (needs a full ETL run), `structural_not_applicable` (no `SEQN` column — see below), or `network_error`.

**Important:** only pass `use_person_check=True` (or omit — it defaults based on `--category`) for the `demographics` category. Every other category will show a false-positive `person_matches > 0` for basically every dataset, because `person` rows are populated by demographics, not by the dataset being classified — that signal is meaningless outside demographics.

Use a **category-specific `--output` filename**. The default `backfill_classification.json` is dietary's — overwriting it loses that record.

### 2. Backfill the "ok" bucket (fast, no re-download needed)

```bash
python3 backfill_dataset_registry.py --ids $(cat examination_ok_ids.txt | tr '\n' ' ')
```

### 3. Check for shared-variable collisions before doing anything else with "ok" datasets

Two datasets sharing the same survey cycle (same `SEQN` pool) sometimes also share identical metadata variable names — e.g. NHANES's `DR1IFF` (individual food records) and `DR1TOT` (daily nutrient totals) both contain `DRDINT`, `WTDRD1`, `DR1LANG`, etc. Naive SEQN+variable-name backfill will attribute *all* of a shared variable's rows to whichever dataset happens to be processed first, silently starving its sibling.

```bash
python3 find_variable_collisions.py --category examination --output examination_collision_pairs.json
python3 build_shared_variable_lookup.py
```

The second command merges *all* `*collision_pairs.json` files it finds into `shared_variables_by_dataset.json` — the single lookup `etl_v3.py` consults at runtime to decide, per variable, whether to use a broad delete-and-reinsert (safe for exclusive variables) or a conservative registry-scoped delete (required for shared ones, to avoid destroying a sibling dataset's legitimate rows). Re-run this after adding a new category's collision data; it won't lose previously-found categories' results as long as their `*_collision_pairs.json` files still exist.

If a collision is found between two datasets that have *already* been ETL'd (so you don't want to re-run their full ETL just to fix attribution), use:
```bash
python3 register_shared_metadata_rows.py <ds_id_a> <ds_id_b>
```
This registers the shared-variable rows to both datasets in `shared_row_registry` and backfills each dataset's exclusive variables into `dataset_row_registry`, without touching or re-inserting any data. For a dataset whose person-constant fields need deduplicating at the source (see below), re-run `etl_v3.py` instead.

### 4. Re-run ETL for any dataset flagged in a collision, or with `never_etld` data

```bash
python3 remove_from_progress.py <ds_id1> <ds_id2> ...
rm dqd/raw/<ds_id>.json  # if a stale report already exists
python3 batch_etl_dqd_new.py --ids <ds_id1> <ds_id2> ...
```

---

## Person-constant field deduplication

Some NHANES files have one row per *item* rather than one row per *person* — e.g. `DR1IFF` has one row per food eaten that day. Admin/weight fields that are genuinely single per-person facts (like `DRDINT`) get redundantly repeated on every one of that person's item rows in the raw file. Naively inserting one `observation`/`measurement` row per raw dataframe row duplicates these fields once per item.

`etl_v3.py` detects this automatically and fixes it at the source: for each variable, it checks whether any person ever has more than one distinct value for it (`_find_person_constant_vars`). If not, it deduplicates to exactly one row per person using their actual value; genuinely per-row-varying variables (e.g. a specific food item's nutrient content) keep the existing one-row-per-raw-row behavior. This applies transparently on every ETL run — no configuration needed.

---

## Reference/lookup datasets (no `SEQN`, no person-level DQD)

Some files aren't person-level records at all — they're vocabulary lookups (NHANES food codes, supplement product/ingredient lists). They have no `SEQN` column, so they can't map to `person`/`measurement`/`observation`, and isolated DQD doesn't apply to them.

Load these into the OMOP CDM's `concept` table instead:

```bash
python3 generate_concept_table_spec.py <ds_id>       # LLM-generated mapping: which column is the concept name/code
python3 harmonize_concept_specs.py <ds_id1> <ds_id2> ...   # normalize domain/vocabulary/concept_class across a family of related datasets
python3 register_vocab_metadata.py <ds_id1> <ds_id2> ...   # ensure the domain/vocabulary/concept_class rows exist
python3 load_concept_data.py <ds_id1> <ds_id2> ...          # actually insert into concept + concept_synonym
```

**Verify any LLM-suggested `domain_id`/`vocabulary_id` against the [official OMOP CDM domain list](https://ohdsi.github.io/CommonDataModel/cdm53.html) before trusting it.** In practice the LLM has confidently invented domains that don't exist (e.g. claiming "Food" is a standard OMOP domain — it isn't; use `Observation`) and confused concept classes for domains (e.g. "Ingredient" is a *concept class* within the `Drug` domain, not a domain itself). `harmonize_concept_specs.py`'s output should always be spot-checked against the real spec, not assumed correct.

`load_concept_data.py` handles cross-dataset duplicate concept codes automatically (e.g. the same USDA food code recurring across multiple NHANES survey years) — if a `(vocabulary_id, concept_code)` pair already exists, it registers the new dataset's attribution in `concept_dataset_registry` (a many-to-many table, same pattern as `shared_row_registry`) instead of inserting a duplicate concept.

`api.py` returns a `structural: true` response with an explanatory message for these datasets' `/api/dqd/result` calls instead of a 404 or an empty report — see `STRUCTURAL_NOT_APPLICABLE` in `api.py` if you're adding a new one to this list.

---

## Extending `etl_v3.py` to a new OMOP table

If an LLM mapping suggests a table beyond `person`/`measurement`/`observation` (e.g. `drug_exposure`), `etl_v3.py` needs explicit support added for it — mappings to unsupported tables are silently dropped. See the `drug_exposure` block in `etl_v3.py` and `_build_drug_exposure_rows` for the pattern to follow: split exclusive vs. shared-variable handling, register rows, and build the INSERT with that table's required `NOT NULL` columns. You'll likely also need a placeholder `concept_id` registered (see `register_drug_exposure_concept.sql`) if the mapping references a standard vocabulary concept your CDM instance doesn't have fully loaded.

---

## View the results

**Option A — via the project's web UI:**
```bash
python3 api.py
```
Then open `http://localhost:8765` and navigate to the dataset.

**Option B — directly in R:**
```r
DataQualityDashboard::viewDqDashboard("dqd/raw/nhanes-demographics-demo_i-2015.json")
```

---

## Output structure

```
dqd/
├── raw/            # DQD JSON results, one per dataset — read by api.py and viewDqDashboard()
├── mapping/        # OMOP mapping JSON generated by etl_v3.py
├── results/        # DQD run logs (log_DqDashboard_*.txt)
└── concept_specs/  # Mapping specs for reference/lookup datasets loaded into `concept`
```

Other files the pipeline depends on:
- `shared_variables_by_dataset.json` — merged output of `build_shared_variable_lookup.py`, consulted by `etl_v3.py` at runtime
- `*_collision_pairs.json` (e.g. `variable_collision_pairs.json`, `examination_collision_pairs.json`) — per-category raw collision detection output, one file per category so they don't overwrite each other
- `*_classification.json` (e.g. `backfill_classification.json`) — per-category output of `classify_backfill_failures.py`

---

## Troubleshooting

- **`rJava` fails to load / `.onLoad failed`** — Java version mismatch. Confirm `java -version` shows 8+, close all R sessions, and reinstall `rJava` and `DatabaseConnector`.
- **"No drivers matching pattern found in folder"** — the `jdbc/` folder is empty or `pathToDriver` in `dqd.R` doesn't match its real location. Re-run `downloadJdbcDrivers()`.
- **`generate_dataset_view_schema.py` aborts with "no rows found in dataset_row_registry"** — the dataset hasn't been ETL'd with `etl_v3.py` yet, or its `batch_progress.json` entry is stale (see below).
- **A batch run reports success in seconds but the report file doesn't exist** — the dataset was likely already marked `done` in `batch_progress.json` from an earlier (possibly stale) run, so `process_one` skipped it without regenerating anything. Use `remove_from_progress.py <ds_id>` to clear it and re-run.
- **A single dataset's DQD run takes 30+ minutes** — check the composite index (step 5) exists on `dataset_row_registry`; this is almost always the cause once the registry has grown large.
- **`DELETE`/`INSERT` seem to silently attribute 0 rows to a dataset that should have data** — check whether those rows are already registered under a *different* `ds_id` due to a variable-name collision (see "shared-variable collisions" above).
- **DQD runs but `api.py` returns 404** — check the file actually landed at `dqd/raw/{ds_id}.json` and that `ds_id` in the URL matches the filename exactly.
- **`executeDdl` fails with permission errors** — the Postgres user needs `CREATE` privileges on the target schema.
