# Changelog

All notable changes to this repository are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); modules are versioned with [Semantic Versioning](https://semver.org/) using tags of the form `<module>-vX.Y.Z` (e.g. `geo-batch-toolkit-v1.0.0`).

## [Unreleased]

## geo-batch-toolkit 1.0.0 — 2026-09-13
### Added
- Batch vector conversion across Shapefile, GeoPackage, GeoJSON, FlatGeobuf, KML and **MapInfo TAB/MIF**.
- Batch reprojection and clipping (vector and raster).
- Raster conversion to Cloud-Optimized GeoTIFF (COG).
- XYZ tile pyramid generation from rasters.
- Parallel batch runner with per-file JSON/CSV run report.
- AWS S3 delivery with dry-run mode.
- Test suite using synthetic data and mocked S3 (`moto`); CI on GitHub Actions.
