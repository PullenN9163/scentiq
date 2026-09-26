# ScentIQ datasets

Raw perfume datasets for loading into the ScentIQ Azure environment.

| File | Size | Contents |
|---|---|---|
| `raw/parfumo_data_clean.csv` | 12 MB | Parfumo scrape. Columns: `Number, Name, Brand, Release_Year, Concentration, Rating_Value, Rating_Count, Main_Accords, Top_Notes, Middle_Notes, Base_Notes, Perfumers, URL`. Missing values are `NA`. |
| `raw/fragrantica_fra_perfumes.zip` | 7 MB | `fra_cleaned.csv` (**semicolon-delimited**: `url;Perfume;Brand;Country;Gender;Rating Value;Rating Count;Year;Top;Middle;Base;Perfumer1;Perfumer2;mainaccord1..5`) and `fra_perfumes.csv` (`Name, Gender, Rating Value, Rating Count, Main Accords, Perfumers, Description, url`). |
| `raw/fragrantica_full_kaggle.zip` | 140 MB (**Git LFS**) | Full Fragrantica corpus ([Kaggle: ledecanteur/fragrantica-perfumes](https://www.kaggle.com/datasets/ledecanteur/fragrantica-perfumes)). `perfumes.csv` (132 MB), `perfumes.jsonl` (530 MB unzipped, one nested JSON record per perfume), `SCHEMA.md` (field reference), preview image. |
| `raw/final_perfume_data.zip` | 1 MB | `final_perfume_data.csv`: `Name, Brand, Description, Notes, Image URL`. |

## Keeping Fragrantica current

`raw/fragrantica_full_kaggle.zip` is Kaggle version 3, a snapshot that is not updated here. The `Refresh datasets` workflow keeps the latest Kaggle release in Azure Blob Storage instead, at `datasets/fragrantica/` in `scentiqstrgdevus`; `fragrantica/latest.json` names the current copy. Load from there for anything that should stay current. See the [dataset refresh runbook](../docs/runbooks/dataset-refresh.md).

The Kaggle dataset is licensed CC BY-NC-SA 4.0: no commercial use, credit Le Decanteur and Fragrantica wherever it is shown, and share derived datasets under the same licence.

## Pulling on the home server

`fragrantica_full_kaggle.zip` is stored with Git LFS, so install LFS before cloning/pulling or you will get a small pointer file instead of the zip:

```sh
git lfs install
git pull            # or: git clone https://github.com/PullenN9163/scentiq.git
git lfs pull        # if the repo was cloned before LFS was installed
```

Then unzip into a working directory (the unzipped files are not committed):

```sh
mkdir -p datasets/extracted
for z in datasets/raw/*.zip; do unzip -o "$z" -d "datasets/extracted/$(basename "$z" .zip)"; done
```
