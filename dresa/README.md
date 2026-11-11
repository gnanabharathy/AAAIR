# DReSA catalogue records

Generates metadata records for registering AAAIR outputs in the DReSA training catalogue
(https://dresa.org.au). Each record is a filled copy of the DReSA training materials
template (`DReSA_Training_Materials_Metadata_Template_v00.docx`, kept outside this
repository), with a Response column added to its three field tables.

## Catalogue structure

Each asset family is one record. Its contents are summarised by category inside the
record rather than registered item by item.

| Record | Covers | Breakdown inside the record |
|---|---|---|
| R0 | AAAIR Resource Hub overview | Links to R1 to R5 |
| R1 | WP2 Open Healthcare Dataset Explorer | Datasets by source, domain and machine learning task |
| R2 | WP3&4 Recommended Analytics and AI Tools | Tool directory: 23 tools in 9 categories, each with a description, licence and training link |
| R3 | WP5 Ethics and Governance Matrix and Checklist | Six recommendations, matrix tiers, licensing key |
| R4 | WP6.4 Course Finder | Featured self-paced courses by domain; aggregate summary of scheduled and one-off offerings |
| R5 | WP6 Training needs and priority tool recommendations | Priority tools and recommendations |
| R6+ | Australian courses that are easy to access | One record per course (optional, `--au-records`) |

Workshops and one-off events are not registered. R4 summarises them and points users to
the Course Finder.

## Running

```bash
python -m venv .venv && .venv/bin/pip install python-docx openpyxl pyyaml
.venv/bin/python dresa/build_dresa_records.py \
    --template "<path>/DReSA_Training_Materials_Metadata_Template_v00.docx" \
    --out "<path>/DReSA_Metadata" --check-dresa
```

- `--check-dresa` searches the public DReSA API for each Australian course title and
  marks courses already listed as materials or events. Title matching is approximate,
  so review the results.
- `--au-records` also writes R6+ records for candidates marked `Separate record`.

## Inputs

- `records.yaml`: narrative field values for R0 to R5 and the R2 tool directory.
- `WP2/data.js`: dataset counts for R1.
- `WP3&4/.../Alltogethertoolsnoborrar.xlsx`: tool home page and training links for R2.
- `WP6/.../WP6.2_database_1_30.06.26.xlsx`: course aggregates, featured courses and
  Australian candidates for R4 and R6+.

## Outputs

- One `.docx` per record.
- `DReSA_Records_Summary.xlsx`, with four sheets:
  - **Records**: one row per record.
  - **Tool directory**: the R2 tools.
  - **Featured courses**: the courses featured in R4.
  - **AU course candidates**: each Australian course, with the proposed treatment and the DReSA check result.

## Open items before submission

- Values marked `[To confirm]` or `[Drafted]` need review. This covers authors and ORCID
  iDs, contact, content provider and licence for project documents.
- URLs point to GitHub until the Nectar-hosted explorer and course finder are live.
- The repository does not state a licence for NHANES data. PTB-XL is CC BY 4.0, checked
  on PhysioNet.
- The PHIDU spreadsheets are one release behind the September 2026 PHIDU release.
- The selected course count is 738 in the database, but the WP6 reports give 736 and 725.
  The records use the database figure.
