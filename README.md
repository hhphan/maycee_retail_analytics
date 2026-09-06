# Maycee Retail Analytics

A focused, single-page retail analytics project built with Python, Streamlit, DuckDB, Pandas, and Plotly. It uses the real public/free Maycee Retail parquet dataset covering 2017-01-01 through 2019-12-31.

This repository is the first public dashboard release in this workstream. It provides a deliberately focused personal companion to the SDataPro dataset: five decision ratios, a three-year sales trend, regional and category comparisons, and one returns diagnostic. The separate SData BI repository is currently private and is not required to run this project.

## Run Locally

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe scripts\fetch_free_data.py
.\.venv\Scripts\python.exe -m streamlit run app\app.py
```

The app opens at `http://127.0.0.1:8501/`. You can also point it at an existing copy of the public export:

```powershell
$env:MAYCEE_FREE_DATA_DIR = "C:\path\to\free_v1_0"
.\.venv\Scripts\python.exe -m streamlit run app\app.py
```

## Validate

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
.\.venv\Scripts\python.exe scripts\check_public_boundary.py
```

The checks are network-free and enforce the public 2017-2019 boundary, scan source files for restricted terms and secret-like values, and ensure local downloaded data is not tracked.

## Data And Attribution

- Dataset: [SDataPro/maycee-retail-dataset](https://huggingface.co/datasets/SDataPro/maycee-retail-dataset)
- Public/free coverage: 2017-01-01 through 2019-12-31
- Dataset licence: CC BY 4.0
- Dashboard code: MIT; first published through this personal repository with the existing SData copyright notice

Downloaded parquet files live under the ignored `data/free_v1_0/` directory and are never committed.
