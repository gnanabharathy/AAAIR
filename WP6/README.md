# WP6: Socio-technical assets, resources and training

Work Package 6 curates online training resources for Australian health researchers
working with advanced analytics and AI, and delivers a pilot Personalised Recommender
System (PRS) that helps researchers find courses matched to their needs.

WP6 holds the only executable software in this repository. If you are looking for
ethics and governance material, see [WP5](../WP5).

## Contents

```
WP6/
└── 06 Resources & Training (WP6)/
    ├── WP6.1/              Training needs analysis from the community survey
    ├── WP6.2_and_6.3/      Course search and extraction protocol, and the course database
    │   └── WP6.2_Extraction_Protocol/
    ├── WP6.4/              PRS design options and two working prototypes
    └── WP6.5/              Prototype user testing, hosting and sustainability
```

16 files in total.

## Sub-packages

### WP6.1: Training needs analysis

`WP6.1_report.docx` reports the community survey that set the project's training
priorities. 99 respondents completed the survey, 77.8% of them based in Australia.
The report covers which tools the community uses and wants to use more, current
skill level by tool, demand for training, a ranking of tools by training demand,
importance and impact, and preferred learning formats, time commitments and barriers
to participation.

### WP6.2 and WP6.3: Search protocol and course database

The search and extraction work uses an LLM-assisted grey literature review method.

| File | What it is |
|------|------------|
| `WP6.2_Report_Search_Protocol.docx` | The search method, screening criteria, known issues and search outcomes |
| `WP6.2_Report_Priority_Tools_Training_Recommendations.docx` | Findings and training recommendations per priority tool |
| `WP6.2_database_1_30.06.26.xlsx` | The course database, dated 30 June 2026 |
| `WP6.2_Extraction_Protocol/extraction_instructions.md` | The extraction protocol, approximately 3,240 words |
| `WP6.2_Extraction_Protocol/6_2_extraction_template.xlsx` | Blank extraction workbook |
| `WP6.2_Extraction_Protocol/tools_and_domains.csv` | The controlled list of tools and domains |
| `WP6.2_Extraction_Protocol/trusted_providers.xlsx` | Vetted training providers |
| `WP6.2_Extraction_Protocol/R_extractions_data_cleaning_script/` | R cleaning pipeline |

**The database** (`WP6.2_database_1_30.06.26.xlsx`) has two sheets:

- `coursework_resources`: 950 course records across 39 fields, covering provider,
  country, health domain relevance, level, delivery platform, format, pace, duration,
  language, primary tools, target audience, cost model and pricing, prerequisites,
  ethics and AI safety coverage, and maintenance and duplicate flags.
- `course_tools`: 2,501 rows mapping courses to the tools they teach.

Of the 950 records, **738 are marked `select` and 212 `reject`**. Rejected courses
are retained deliberately so that screening decisions can be revisited if the
criteria change.

**The controlled vocabulary** (`tools_and_domains.csv`) lists 85 tools across six
domains:

| Domain | Tools |
|--------|-------|
| Domain-specific tools | 25 |
| Programming and environments | 17 |
| Conversational AI and coding co-pilots | 13 |
| Analysis methods | 12 |
| ML frameworks and methods | 11 |
| No-code and low-code | 7 |

Each row records its provenance, most commonly a structured survey question (50),
a free-text survey response (13), or discovery during the WP6.2 searches.

`trusted_providers.xlsx` lists 112 vetted providers used in Phase 1 of the search.

The search protocol was executed across **22 extraction sessions between March and
June 2026**, combining trusted provider catalogues (Phase 1) with open web searches
(Phase 2).

### WP6.4: Personalised Recommender System prototypes

`WP6.4_Report.docx` evaluates four design approaches against implementation
readiness and maintainability:

1. Guided needs assessment wizard
2. Faceted filter and search dashboard
3. AI-powered natural language query interface
4. Course comparison and shortlisting tool

Approaches 1 and 2 were built as working prototypes.

| File | Prototype |
|------|-----------|
| `Wizard_prototype1.html` | Approach 1, "ARDC Course Finder, Guided Needs Assessment" |
| `dashboard_prototype1.html` | Approach 2, "Health Research Analytics & AI, Course Finder" |
| `dashboard_prototype2.html` | Approach 2, second variant |
| `dashboard_prototype2.qmd` | Quarto source for `dashboard_prototype2.html` |

Both dashboards embed the 738 selected courses directly in the page as a `COURSES`
JavaScript constant. The wizard embeds its own course set. All three run entirely in
the browser with no server, no build step and no network calls for data.

### WP6.5: User testing and sustainability

`WP6.5_Report_Prototype_User_Testing.docx` evaluates the two prototypes. Feedback
came from eight reviewers, comprising PhD students and researchers from the QUT
Centre for Data Science working in applied statistics, health, biomedical science
and computer science. Reviewer preference between the two prototypes was split, and
several reviewers changed their preference during use. The wizard was consistently
described as the more approachable entry point.

The report also covers hosting pathways, a prioritised design-change register,
pre-launch fixes, budget estimates and risks. It identifies the principal
sustainability risk as informational rather than technical: the tool loses value as
the underlying course database ages. It proposes moving from a manual protocol to an
agent-based approach for automating database updates.

## Running the prototypes

**The prototypes will not render if you click the file in GitHub.**
`raw.githubusercontent.com` serves HTML as `text/plain` with `nosniff`, and GitHub
Pages is not enabled on this repository, so you will see source code rather than the
application. You must download the file and open it locally.

```bash
BASE="https://raw.githubusercontent.com/gnanabharathy/AAAIR/main/WP6/06%20Resources%20%26%20Training%20(WP6)/WP6.4"

curl -L -o wizard.html            "$BASE/Wizard_prototype1.html"
curl -L -o dashboard1.html        "$BASE/dashboard_prototype1.html"
curl -L -o dashboard2.html        "$BASE/dashboard_prototype2.html"

open wizard.html      # macOS
xdg-open wizard.html  # Linux
```

No installation, server or internet connection is needed once downloaded. The wizard
fetches Google Fonts and the ARDC logo from the web for styling only, so it will
still work offline with slightly different typography.

To check out WP6 alone rather than cloning the full repository (approximately
537 MB):

```bash
git clone --filter=blob:none --sparse https://github.com/gnanabharathy/AAAIR.git
cd AAAIR
git sparse-checkout set WP6
```

Directory names contain spaces, ampersands and parentheses. Quote paths in shell
commands and percent-encode them in URLs.

## Rebuilding the data pipeline

**The R pipeline does not currently run outside its author's machine.** Treat the
committed prototypes as the working artefacts and the pipeline as a record of method
until the issues below are resolved.

`WP6.2_Extraction_Protocol/R_extractions_data_cleaning_script/01_data_cleaning_script.R`
reads from and writes to hardcoded absolute Windows paths in two separate
repositories that are not public:

```r
path_xlsx <- "C:/Users/robertj9/Repos/ARDC_6.2/08_reextraction/compiled_reextraction_batches.xlsx"
path_out  <- "C:/Users/robertj9/Repos/ARDC_6.4/01_data"
```

Three referenced files are absent from this repository:

| Missing file | Role |
|--------------|------|
| `compiled_reextraction_batches.xlsx` | The script's input |
| `6.4_cleaned_extraction_data.csv` | The script's main output, and the input to `dashboard_prototype2.qmd` |
| `validate_outputs.R` | Sourced at line 369 |

`dashboard_prototype2.qmd` reads `../01_data/6.4_cleaned_extraction_data.csv`, so the
Quarto document cannot be re-rendered and the dashboard's course data cannot be
refreshed.

To make the pipeline reproducible, three changes are needed:

1. Replace the two absolute paths with relative paths, ideally using the `here`
   package.
2. Commit `compiled_reextraction_batches.xlsx` (or document where it lives),
   `6.4_cleaned_extraction_data.csv` and `validate_outputs.R`.
3. Correct `load_packages.R`, which installs `shiny`, `DT`, `bslib`, `reactable` and
   `crosstalk`. None of these are used by the cleaning script or the Quarto document,
   which need `readr`, `readxl`, `dplyr`, `stringr` and `jsonlite`. The current list
   appears to be a leftover from an earlier Shiny-based approach.

## Known gaps

- **No WP6.3 deliverable is separately identifiable.** The folder is named
  `WP6.2_and_6.3` but every file inside is labelled 6.2. Whether WP6.3 is folded into
  the WP6.2 reports or still outstanding is not recorded anywhere in the repository.
- **The two dashboard variants are undocumented.** `dashboard_prototype1.html` and
  `dashboard_prototype2.html` are 3,014,988 and 3,016,045 bytes respectively and
  carry the same page title. What differs between them, and which one supersedes the
  other, is not stated. Only variant 2 has committed Quarto source.
- **No `.gitignore`.** `.DS_Store` files are committed at the WP6 root and in three
  subdirectories.

## Provenance

The course database and prototypes derive from the WP6.1 community survey (99
respondents) and 22 LLM-assisted extraction sessions run between March and June 2026.
Database version is dated 30 June 2026. Course data ages quickly, and WP6.5 treats
currency as the main sustainability risk, so check the database date before relying
on pricing, start dates or enrolment status.

---

Part of the [AAAIR](../README.md) project (ARDC-ADSN Advanced Analytics and AI
Resource Hub). See the root README for the full work package structure.
