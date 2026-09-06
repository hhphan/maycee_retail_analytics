# Public Data Boundary

This personal project uses only the Maycee Retail public/free dataset from
`SDataPro/maycee-retail-dataset`, covering 2017-01-01 through 2019-12-31.

The repository may contain source code, tests, documentation, and placeholder
paths. It must not contain restricted commercial data, access credentials,
entitlement files, fulfilment records, private retrieval locations, or customer
information. Downloaded parquet files stay in ignored `data/free_v1_0/`.

Run the automated boundary check before review:

```powershell
.\.venv\Scripts\python.exe scripts\check_public_boundary.py
```
