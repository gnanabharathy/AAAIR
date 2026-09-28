# Dataset Coverage

This file tracks two different things, which are easy to conflate but genuinely separate:

- **Extracted** — the dataset's variable metadata has been pulled into `schema.json` (via `extractor.py`) and is browsable in the UI's schema page.
- **DQD status** — the dataset has been loaded into the OMOP CDM and has an isolated Data Quality Dashboard report, scoped to just that dataset's own data (see [DQD.md](DQD.md) for how this works).

A dataset can be extracted with no DQD status at all (metadata browsable, no quality report yet), or fully extracted *and* have a complete DQD report. Some datasets — MIMIC-IV's restricted-access tables, PHIDU's region-level statistics — never get either, for documented structural reasons rather than being unfinished work.

Run `python3 scan_nhanes.py` to refresh the available counts for NHANES.

---

## NHANES — National Health and Nutrition Examination Survey

**Source:** https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx
**Cycles:** 1999–2000 to 2021–2023
**Scan script:** `scan_nhanes.py`
**Batch file:** `datasets_nhanes_full.csv`

### Metadata extraction

| Category | Description | Available | Extracted |
|----------|-------------|-----------|-----------|
| Demographics | Age, sex, race, income, household variables | 12 | 12 |
| Dietary | Food intake, nutrient values, 24-hour recall | 125 | 125 |
| Examination | Anthropometrics, blood pressure, BMI, vitals | 191 | 191 |
| Laboratory | Blood, urine, biochemistry, metabolic markers | 766 | 766 |
| Questionnaire | Health history, lifestyle, smoking, alcohol | 506 | 506 |
| **Total** | | **1600** | **1600** |

> To extract all remaining datasets:
> ```bash
> python3 extractor.py --batch datasets_nhanes_full.csv
> ```

### DQD status (isolated per-dataset reports)

| Category | Total | Reference/lookup only | Not currently supported | DQD complete |
|----------|-------|------------------------|--------------------------|--------------|
| Demographics | 12 | 0 | 0 | ✅ 12 / 12 |
| Dietary | 125 | 24 (loaded into `concept` table instead — see below) | 0 | ✅ 101 / 101 |
| Examination | 191 | 0 | 11 (see below) | ✅ 180 / 180 eligible datasets |
| Laboratory | 766 | — | — | Not started |
| Questionnaire | 506 | — | — | Not started |

**Dietary's 24 reference/lookup datasets** (food codes, supplement ingredient/product lists) have no participant identifier (`SEQN`), so DQD doesn't apply to them the way it does to person-level survey data. Their content is instead loaded into the OMOP CDM's `concept` table as vocabulary entries — see `dqd/concept_specs/` for the mapping specs, and [DQD.md](DQD.md#reference-lookup-datasets) for how this works.

**Examination's 11 not-currently-supported datasets** are NHANES accelerometer/spirometer files, and split into two genuinely different reasons:
- **6 datasets** (`PAX80_G/H`, `PAXLUX_G/H`, `PAXMIN_G/H` — 2011–2014 cycle raw accelerometer data) were never published as a single per-person table at all. CDC distributes them as one archive per participant on their FTP server (roughly 1 TB compressed in total). This project's ETL pipeline processes single tabular files and can't currently ingest a per-participant archive format.
- **5 datasets** (`PAXRAW_C/D`, `SPXRAW_E/F/G` — 2003–2011 cycle raw accelerometer/spirometry data) *do* have a normal, `SEQN`-linked table structure (confirmed from their own documentation codebooks), but CDC distributes them as a large `.ZIP` archive rather than the plain `.xpt` file this project's extractor expects at that URL. This is a pipeline limitation, not a data availability issue, and is a planned future improvement — see `DATA_ZIPPED_NOT_YET_SUPPORTED` in `api.py`.

**Data linkage:** all 1,600 NHANES datasets have a "Data linkage" note on their card, generated from a deterministic rule (not hand-written per dataset) — every dataset links to its survey cycle's demographics file, and to every other dataset from that same cycle, via `SEQN`. The 24 dietary reference tables (and one cross-cycle drug-code dictionary, `RXQ_DRUG`) instead note that they aren't person-linkable. See `generate_nhanes_linkage.py`.

---

## PHIDU — Social Health Atlas of Australia

**Source:** https://phidu.torrens.edu.au/social-health-atlases/data
**Publisher:** PHIDU, Torrens University Australia
**License:** Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Australia
**Extractor script:** `extractor_phidu.py`

PHIDU reports region-level population health statistics (rates and counts for a state or health area), not individual-person records. It has no participant-level rows to map into the OMOP CDM's person-centric tables, so **DQD does not apply to any PHIDU dataset** — they're browsable for their metadata/data tables only.

| Category | Description | Files | Sheets/File | Extracted |
|----------|-------------|-------|-------------|-----------|
| PHA by location | Population Health Area data by state/territory | 9 | 873 | 873 |
| PHA by topic | Health status, services, social determinants by PHA | 3 | 101 | 101 |
| LGA | Local Government Area data | 8 | TBD | 0 |
| PHN | Primary Health Network data | 2 | TBD | 0 |
| Socioeconomic | Socioeconomic Disadvantage of Area data | 3 | TBD | 0 |
| Remoteness | Remoteness Area data | 2 | TBD | 0 |
| ATSI | Aboriginal & Torres Strait Islander data | 6 | TBD | 0 |
| Indigenous Comparison | Indigenous Status Comparison data | 3 | TBD | 0 |
| **Total** | | **36** | | **974** |

**Data linkage:** not yet written for PHIDU. A likely rule (shared geography codes linking the "by location" and "by topic" sheets) hasn't been implemented yet.

---

## MIMIC-IV — Medical Information Mart for Intensive Care

**Source:** https://physionet.org/content/mimiciv/3.1/ (hosp/icu modules), https://physionet.org/content/mimic-iv-ed/2.2/ (ED module)
**Publisher:** MIT Laboratory for Computational Physiology, via PhysioNet
**Access:** Requires PhysioNet credentialed access — this project cannot redistribute the data or its schema

MIMIC-IV's data is not extracted, browsable, or DQD-checked in this tool at all — every card exists only to point to the official documentation and explain why. This is a deliberate, permanent state for this data source, not an in-progress task.

| Module | Tables | Cards |
|--------|--------|-------|
| Hospital (hosp) | patients, admissions, transfers, labevents, microbiologyevents, poe, emar, prescriptions, pharmacy, diagnoses/procedures (ICD), hcpcsevents, drgcodes, omr, services, provider, and their dictionary tables | 23 |
| ICU | icustays, chartevents, inputevents, outputevents, procedureevents, datetimeevents, ingredientevents, caregiver, and d_items | 9 |
| Emergency Department (ED) | edstays, diagnosis, medrecon, pyxis, triage, vitalsign | 6 |
| **Total** | | **38** |

Not yet added: MIMIC-IV-Note (clinical notes) and MIMIC-CXR (chest X-ray + reports) — separate PhysioNet-hosted projects in the same family, out of scope for now.

**Data linkage:** all 38 cards have a real, table-specific linkage note (e.g. `labevents` links to `patients`/`admissions` via `subject_id`/`hadm_id`, and to `d_labitems` via `itemid`) drawn from MIMIC-IV's own documented foreign-key relationships — see `mimic_iv_linkage.json`.

---

## Other Datasets

**PTB-XL** — 12-lead ECG records, extracted with a complete isolated DQD report. All 28 documented variables are loaded across `person`, `measurement`, `observation`, `condition_occurrence`, and `note` (`sex`/`patient_id` → person; `age`/`height`/`weight`/`extra_beats` → measurement; diagnostic/device/site metadata → observation; SCP-ECG diagnostic statements → condition_occurrence; free-text reports → note). `filename_hr`/`filename_lr` are deliberately not loaded — catalog-only pointers to the raw waveform files, not clinical data. See `etl_ptbxl_v2.py`.

**Data linkage:** not yet written for PTB-XL.

---

## FAIRness assessment

Every dataset card has a "Check FAIRness ↗" button that copies the dataset's documentation URL/DOI to the clipboard and opens [F-UJI](https://www.f-uji.net/), so anyone can run a live FAIR (Findable, Accessible, Interoperable, Reusable) assessment on demand rather than this project storing a point-in-time score. In practice, F-UJI's scoring depends heavily on whether the source publishes a DOI with structured metadata: PhysioNet-hosted sources (PTB-XL, MIMIC-IV) score meaningfully higher than CDC's NHANES pages or PHIDU's plain Excel downloads, neither of which carry a DOI.

---

## How to add a new data source

1. Find the documentation URL for the dataset
2. Add to `datasets.csv`
3. See [EXTRACTION.md](EXTRACTION.md) for the full extraction workflow, and [DQD.md](DQD.md) if you also want an isolated quality report for it.
