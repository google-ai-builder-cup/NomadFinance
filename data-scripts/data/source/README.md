# Source data

Large raw files live here but are **not committed** (`.gitignore` excludes `*.xlsx` and `*.zip`). Each person downloads them once.

## World Bank RPW (Remittance Prices Worldwide)

| | |
|---|---|
| File name | `rpw_dataset_2011_2025_q1.xlsx` |
| Save as | `data-scripts/data/source/rpw_dataset_2011_2025_q1.xlsx` |
| Size | about 49 MB |
| Covers | 2011 to Q1 2025 (latest available from the World Bank) |
| Used by | `python -m src.loaders.world_bank` (NF-P1-015) |

Download in a normal browser (the direct link sits behind a Cloudflare check, so `curl` and scripts are blocked):

1. Open <https://remittanceprices.worldbank.org/data-download>.
2. Click the link labelled "RPW dataset request form". It downloads the `.xlsx` file.
3. Move the file to the path above. Keep the exact file name.

Attribution is required wherever the data is shown: "The World Bank, Remittance Prices Worldwide, available at http://remittanceprices.worldbank.org". Do not use the World Bank logo or imply endorsement.

`labor-laws/` holds the curated ILO NATLEX JSON files, which are committed.
