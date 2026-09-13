# Changelog

All notable changes to this repository are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); modules are versioned with [Semantic Versioning](https://semver.org/) using tags of the form `<module>-vX.Y.Z` (e.g. `geo-batch-toolkit-v1.0.0`).

## [Unreleased]

## geo-batch-toolkit 1.1.1 — 2026-09-13
### Fixed
- FlatGeobuf output no longer takes the incremental-write path regardless of source
  size — its append support redoes significant spatial-index work on every chunk
  (5613s vs 661s single-shot on the 24GB roads test file), so `vector-convert --to fgb`
  always writes the output once. This is a deliberate trade-off: very large FGB
  conversions can still hit the memory ceiling incremental writes exist to avoid;
  `--to gpkg` is the safer choice for large sources. A log line notes when a large
  FGB source skips incremental writes for this reason. Verified against the real
  24GB file: 592.9s, back in line with the original single-shot baseline.
- Progress reporting no longer requires crossing the chunk-write threshold: every
  `vector-convert` reads its input in batches (`--chunk-size`) purely to report
  progress, then either writes incrementally (large, non-FGB sources) or accumulates
  and writes once (everything else, including small files and all FGB output) —
  so a live progress bar now shows for any single-file conversion, not just large ones.

## geo-batch-toolkit 1.1.0 — 2026-09-13
### Added
- Chunked vector conversion: `vector-convert` now reads/transforms/writes in feature
  batches once a source dataset crosses `--chunk-threshold-gb` (default 5GB), instead
  of loading it into memory whole. `--chunk-size` controls the batch size.
- Live `tqdm` progress bar when converting a single large file with `--workers 1`;
  a plain per-chunk log line otherwise (multiple files / parallel workers).
### Fixed
- Real-world testing on a 24GB OSM roads Shapefile surfaced RAM thrashing on large
  datasets; the chunked path above removes the whole-file-in-memory bottleneck for
  vector conversions. Raster's masked-clip path has the same theoretical risk and is
  a planned follow-up, not addressed here.
### Known issues
- Chunked conversion **to FlatGeobuf** is currently much slower than a single-shot
  conversion of the same file (5613s vs 661s on the 24GB roads test file) — FGB's
  append support appears to redo significant spatial-index work on every chunk.
  Chunking **to GPKG** does not have this problem (405s on the same file, faster
  than the single-shot FGB run). Until fixed: prefer `--to gpkg` for large sources;
  a chunk-to-GPKG-then-translate-once approach for FGB output is planned.

## geo-batch-toolkit 1.0.0 — 2026-09-13
### Added
- Batch vector conversion across Shapefile, GeoPackage, GeoJSON, FlatGeobuf, KML and **MapInfo TAB/MIF**.
- Batch reprojection and clipping (vector and raster).
- Raster conversion to Cloud-Optimized GeoTIFF (COG).
- XYZ tile pyramid generation from rasters.
- Parallel batch runner with per-file JSON/CSV run report.
- AWS S3 delivery with dry-run mode.
- Test suite using synthetic data and mocked S3 (`moto`); CI on GitHub Actions.
