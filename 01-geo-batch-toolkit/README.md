# 01 · geo-batch-toolkit

[![CI](https://github.com/shivateja2026/gis-dev-portfolio/actions/workflows/ci.yml/badge.svg)](https://github.com/shivateja2026/gis-dev-portfolio/actions)
![Python](https://img.shields.io/badge/python-3.10%20|%203.12-blue) ![Version](https://img.shields.io/badge/version-1.1.1-green)

A command-line toolkit that **batch-processes large geospatial datasets**: format conversion (including **MapInfo TAB/MIF**), reprojection, clipping, **Cloud-Optimized GeoTIFF** output, **XYZ tile pyramid** generation, and delivery to **AWS S3**, with a per-file run report for every batch.

Built for the everyday data-conversion work in GIS delivery projects: a client sends 300 files in mixed formats and CRSs, and they need to come back consistent, validated and hosted.

## Features

| Command | What it does |
|---|---|
| `geobatch vector-convert` | Converts every Shapefile / GeoPackage / GeoJSON / FlatGeobuf / KML / MapInfo TAB / MIF in a folder into one target format, with optional reprojection and clipping (bbox or polygon mask) |
| `geobatch raster-convert` | Reprojects/clips rasters and writes Cloud-Optimized GeoTIFFs (DEFLATE), with choice of resampling |
| `geobatch tiles` | Builds a `{z}/{x}/{y}.png` Web Mercator tile pyramid with transparency for nodata, `metadata.json` (TileJSON) and a Leaflet `preview.html` |
| `geobatch s3-upload` | Uploads a results folder to S3 with correct content types; `--dry-run` supported |
| `geobatch info` | Prints CRS, bounds, size, schema and COG status as JSON |
| `geobatch formats` | Lists supported output formats |

Every batch command runs files in parallel (`--workers N`), **isolates failures** (one corrupt file is logged and reported, and the rest of the batch continues), and writes `run_report.json` + `run_report.csv` (status, output path, time taken, error per file). `vector-convert` reads every dataset in batches, with a live progress bar when converting a single file (`--workers 1`); above `--chunk-threshold-gb` (default 5GB) it also writes incrementally instead of loading the whole dataset into memory, except for FlatGeobuf which always writes once.

## Quick start

```bash
cd 01-geo-batch-toolkit
python -m venv .venv
# Windows: .venv\Scripts\activate    Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"

pytest -v                  # 19 tests, synthetic data + mocked S3, no downloads needed
python examples/demo.py    # full end-to-end run on generated sample data
```

GDAL is bundled inside the `pyogrio` and `rasterio` wheels, so no separate GDAL/OSGeo4W install is needed on Windows.

## Usage examples

```bash
# 300 mixed-format client files → GeoPackage in UTM 44N, 4 processes
geobatch vector-convert ./client_drop ./gpkg_utm --to gpkg --crs EPSG:32644 --workers 4

# Legacy MapInfo tables → GeoJSON for a web map
geobatch vector-convert ./mapinfo_archive ./web --to geojson

# Clip everything to a district boundary
geobatch vector-convert ./state_layers ./adilabad --to gpkg --mask ./adilabad_boundary.gpkg

# DEM mosaic tiles → COG in UTM (bilinear for continuous data)
geobatch raster-convert ./srtm ./cog --crs EPSG:32644 --resampling bilinear

# Tile pyramid for a web viewer, then deliver
geobatch tiles ./cog/dem.tif ./tiles --zoom 8-14
geobatch s3-upload ./tiles --bucket bmgt-deliveries --prefix client-a/2026-09/dem
```

### Sample run (from `examples/demo.py`)

```
$ geobatch vector-convert out/input_vector out/mapinfo --to tab
Found 3 vector datasets
OK    facilities.shp -> facilities.tab (0.01s)
OK    grid.geojson -> grid.tab (0.01s)
OK    legacy_facilities.tab -> legacy_facilities.tab (0.02s)
3/3 succeeded. Report: run_report.json / run_report.csv

$ geobatch tiles out/input_raster/dem.tif out/tiles --zoom 9-13
290 tiles written (0 empty skipped), zoom 9-13.
```

## Design decisions

- **pyogrio engine** instead of Fiona: vectorised I/O through GDAL, much faster on large files.
- **Discovery by primary file only** (`.shp`, `.tab`, …): sidecars (`.dbf`, `.dat`, `.map`, `.id`) are never processed as separate datasets.
- **No silent reprojection:** reprojection happens only when `--crs` is given. The one exception is KML/GeoJSON, whose specifications mandate WGS84; that is logged as a warning.
- **Clipping happens after reprojection**, so `--bbox` is always in the output CRS (documented in `--help`).
- **Resampling is explicit:** `nearest` by default (safe for categorical LULC rasters); `bilinear`/`cubic` for continuous data like DEMs.
- **Idempotent reruns:** old outputs and their sidecars are removed before writing, so reruns never append duplicates.
- **`vector-convert` always reads in batches** (`--chunk-size`, default 200k features), so progress is reported for every conversion regardless of size — not just large ones. **Writes** only stream incrementally above `--chunk-threshold-gb` (default 5GB); below it, and always for FlatGeobuf, batches are accumulated and written once — same memory profile as a single-shot conversion. **FlatGeobuf is exempt from incremental writes by design:** real-world testing on OSM road data (24GB) showed its append support redoes spatial-index work per chunk (5613s chunked vs 661s single-shot on the same file), so `--to fgb` always writes once regardless of size — a deliberate trade-off of the memory-safety benefit for speed on the common case. `--to gpkg` is the safer choice for very large sources.
- **COG via GDAL's COG driver:** internal tiling and overviews, so outputs can be streamed over HTTP range requests directly from S3.
- **Tiles use one global stretch** (min/max computed once at overview resolution), so neighbouring tiles don't show seams.
- **No credentials in code:** S3 uses the standard AWS credential chain (env vars, `~/.aws`, IAM role).

## Project layout

```
01-geo-batch-toolkit/
├── src/geobatch/
│   ├── cli.py        # click CLI
│   ├── formats.py    # format registry + discovery rules
│   ├── vector.py     # convert / reproject / clip
│   ├── raster.py     # reproject / clip / COG
│   ├── tiles.py      # XYZ pyramid + TileJSON + preview
│   ├── s3.py         # delivery
│   ├── batch.py      # parallel runner + run reports
│   └── info.py       # dataset inspection
├── tests/            # pytest, synthetic data, moto-mocked S3
└── examples/demo.py  # end-to-end demo
```

## Honesty table

| This module demonstrates | It does not claim |
|---|---|
| Batch conversion/reprojection/clipping across 7 vector formats incl. MapInfo | Use of MapInfo Professional (the desktop product); MapInfo *data formats* are handled via GDAL |
| COG creation, XYZ tiling, S3 delivery | Production tile serving at scale (CDN, cache invalidation) |
| Tested behaviour on synthetic data, plus real OSM road data up to 24GB | Benchmarks across the full range of production dataset sizes/shapes; raster's masked-clip path is not yet chunked, unlike vector |
| Parallel processing with failure isolation | Distributed processing (Dask/Spark) |

The ArcGIS equivalent (arcpy script tools) is in module `02-arcpy-toolbox`.
