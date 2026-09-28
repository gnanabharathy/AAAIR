import pandas as pd

db = pd.read_csv('ptbxl_database.csv', index_col='ecg_id')
print(f"Total records: {len(db)}\n")

for col in ['device', 'nurse', 'site', 'validated_by', 'extra_beats',
            'filename_hr', 'filename_lr']:
    if col not in db.columns:
        print(f"{col}: COLUMN NOT FOUND in CSV")
        continue
    non_null = db[col].notna().sum()
    print(f"{col}: {non_null} of {len(db)} non-null "
          f"({100*non_null/len(db):.1f}%)")
    if non_null > 0:
        print(f"  sample values: {db[col].dropna().unique()[:5]}")
