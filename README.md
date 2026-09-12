# GIS Developer Portfolio · Shivateja Pampattiwar

M.Sc. Geoinformatics (CGPA 9.06, First Division with Distinction) · Founder, [Bhoo-Mitra Geo Technologies](https://www.bmgt.in) · former Project Associate on an IIRS-ISRO sponsored permafrost hazard project.

A monorepo of working GIS development projects: batch data conversion, Esri/QGIS tooling, automation, raster tiling, dashboards, .NET, and delivery documentation. Each module has its own README, tests and an **honesty table** stating what it does and does not demonstrate.

## Modules

| # | Module | Status | Stack |
|---|---|---|---|
| 01 | [geo-batch-toolkit](01-geo-batch-toolkit/) | ✅ v1.0.0 | Python, GDAL (pyogrio/rasterio), AWS S3, click, pytest |
| 02 | arcpy-toolbox | 🗓 Sep 17 | ArcGIS Pro, arcpy, Python toolbox |
| 03 | qgis-plugin | 🗓 Sep 15–16 | PyQGIS, PyQt/Qt Designer |
| 04 | automation (shell + web API) | 🗓 Sep 18 | bash, Python, REST APIs, cron |
| 05 | raster-tiling + source catalogue runbook, FME | 🗓 Sep 19–20 | STAC, GDAL, FME Workbench |
| 06 | geo-dashboard with role-based access | 🗓 Sep 21–23 | JavaScript, ArcGIS REST, LDAP/AD-style RBAC |
| 07 | dotnet (C# + VB.NET) | 🗓 Sep 24 | .NET 8 |
| 08 | vba automation | 🗓 Sep 25 | Excel VBA |
| 09 | telecom GIS mini-project | 🗓 Sep 25 | Python, network data |
| 10 | docs site, training, videos, newsletter | 🗓 Sep 27–28 | MkDocs, Confluence storage format |
| 11 | delivery: proposal, pricing models, agile artefacts, daily status | 🔄 ongoing | GitHub Projects |

## How this repo is run

- **Configuration management:** GitHub Flow, protected `main`, Conventional Commits, SemVer tags per module. See [CONTRIBUTING.md](CONTRIBUTING.md).
- **CI:** lint + tests on every push/PR ([workflow](.github/workflows/ci.yml)).
- **Daily reporting:** a status report is committed every working day in [`docs/daily-status/`](docs/daily-status/).
- **Changes:** [CHANGELOG.md](CHANGELOG.md).

## Contact

pampattiwarshivateja@gmail.com · [LinkedIn](https://www.linkedin.com/in/shivateja-pampattiwar) · [bmgt.in](https://www.bmgt.in)
