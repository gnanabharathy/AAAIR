# Dataset Coverage

This file tracks all datasets available and extracted in this tool.
Run `python3 scan_nhanes.py` to refresh the available counts.

---

## NHANES — National Health and Nutrition Examination Survey

**Source:** https://wwwn.cdc.gov/nchs/nhanes/continuousnhanes/default.aspx  
**Cycles:** 1999–2000 to 2021–2023  
**Scan script:** `scan_nhanes.py`  
**Batch file:** `datasets_nhanes_full.csv`

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

---

## PHIDU — Social Health Atlas of Australia

**Source:** https://phidu.torrens.edu.au/social-health-atlases/data  
**Publisher:** PHIDU, Torrens University Australia  
**License:** Creative Commons Attribution-NonCommercial-ShareAlike 3.0 Australia  
**Extractor script:** `extractor_phidu.py`

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

## Other Datasets

---

## How to add a new data source

1. Find the documentation URL for the dataset
2. Add to `datasets.csv`:
