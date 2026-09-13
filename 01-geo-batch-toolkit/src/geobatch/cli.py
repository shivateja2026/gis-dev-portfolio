"""Command-line interface: ``geobatch --help``."""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import click
from tqdm import tqdm

from . import __version__
from .batch import run_batch
from .formats import VECTOR_FORMATS, discover
from .info import describe
from .raster import convert_raster
from .s3 import upload_directory
from .tiles import generate_xyz_tiles
from .vector import CHUNK_SIZE_FEATURES, CHUNK_THRESHOLD_BYTES, convert_vector

log = logging.getLogger(__name__)


def _bbox(ctx, param, value):
    if value is None:
        return None
    try:
        parts = tuple(float(v) for v in value.split(","))
        assert len(parts) == 4 and parts[0] < parts[2] and parts[1] < parts[3]
        return parts
    except (ValueError, AssertionError):
        raise click.BadParameter("use minx,miny,maxx,maxy (e.g. 78.0,19.0,79.0,20.0)") from None


def _zoom(ctx, param, value):
    try:
        lo, hi = (int(v) for v in value.split("-"))
        assert 0 <= lo <= hi <= 22
        return lo, hi
    except (ValueError, AssertionError):
        raise click.BadParameter("use MIN-MAX, e.g. 8-12 (0-22)") from None


@click.group()
@click.version_option(__version__)
@click.option("-v", "--verbose", is_flag=True, help="Debug logging.")
def main(verbose: bool) -> None:
    """Batch-process large geospatial datasets."""
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        datefmt="%H:%M:%S",
    )


def _log_progress_cb(processed: int, total: int) -> None:
    log.info("%d/%d features (%.0f%%)", processed, total, 100 * processed / total)


def _tqdm_progress_cb():
    """Live bar for a single file processed by a single worker; picklable fallback otherwise."""
    bar = None

    def cb(processed: int, total: int) -> None:
        nonlocal bar
        if bar is None:
            bar = tqdm(total=total, unit="feat", desc="Converting", leave=False)
        bar.update(processed - bar.n)
        if processed >= total:
            bar.close()

    return cb


def _summarise(results) -> None:
    ok = sum(r.status == "ok" for r in results)
    click.echo(f"\n{ok}/{len(results)} succeeded. Report: run_report.json / run_report.csv")
    if ok < len(results):
        sys.exit(1)


@main.command("vector-convert")
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False))
@click.argument("output_dir", type=click.Path(file_okay=False))
@click.option("--to", "fmt", required=True, type=click.Choice(sorted(VECTOR_FORMATS)))
@click.option("--crs", "target_crs", help="Target CRS, e.g. EPSG:32644")
@click.option("--bbox", callback=_bbox, help="Clip box in OUTPUT CRS: minx,miny,maxx,maxy")
@click.option("--mask", "mask_path", type=click.Path(exists=True), help="Clip to polygon layer")
@click.option("--workers", default=1, show_default=True, help="Parallel processes")
@click.option("--chunk-threshold-gb", default=CHUNK_THRESHOLD_BYTES / 1024**3, show_default=True,
              help="Write in batches (not just read) above this source size, to bound "
                   "memory use - always skipped for FGB, which writes once regardless")
@click.option("--chunk-size", default=CHUNK_SIZE_FEATURES, show_default=True,
              help="Features per read batch (also the write batch size, once chunked)")
def vector_convert(input_dir, output_dir, fmt, target_crs, bbox, mask_path, workers,
                   chunk_threshold_gb, chunk_size):
    """Convert every vector dataset in INPUT_DIR (Shapefile, GPKG, GeoJSON, FGB, KML, TAB, MIF)."""
    files = discover(input_dir, "vector")
    click.echo(f"Found {len(files)} vector datasets")
    progress_cb = _tqdm_progress_cb() if len(files) == 1 and workers <= 1 else _log_progress_cb
    results = run_batch(convert_vector, files, output_dir, workers, out_dir=output_dir, fmt=fmt,
                        target_crs=target_crs, bbox=bbox, mask_path=mask_path,
                        chunk_threshold=int(chunk_threshold_gb * 1024**3), chunk_size=chunk_size,
                        progress_cb=progress_cb)
    _summarise(results)


@main.command("raster-convert")
@click.argument("input_dir", type=click.Path(exists=True, file_okay=False))
@click.argument("output_dir", type=click.Path(file_okay=False))
@click.option("--crs", "target_crs", help="Target CRS, e.g. EPSG:32644")
@click.option("--bbox", callback=_bbox, help="Clip box in OUTPUT CRS")
@click.option("--no-cog", is_flag=True, help="Write plain GeoTIFF instead of COG")
@click.option("--resampling", default="nearest", show_default=True,
              type=click.Choice(["nearest", "bilinear", "cubic"]))
@click.option("--workers", default=1, show_default=True)
def raster_convert(input_dir, output_dir, target_crs, bbox, no_cog, resampling, workers):
    """Reproject/clip every raster in INPUT_DIR and write Cloud-Optimized GeoTIFFs."""
    files = discover(input_dir, "raster")
    click.echo(f"Found {len(files)} rasters")
    results = run_batch(convert_raster, files, output_dir, workers, out_dir=output_dir,
                        target_crs=target_crs, bbox=bbox, cog=not no_cog, resampling=resampling)
    _summarise(results)


@main.command()
@click.argument("raster", type=click.Path(exists=True, dir_okay=False))
@click.argument("output_dir", type=click.Path(file_okay=False))
@click.option("--zoom", default="8-12", show_default=True, callback=_zoom)
def tiles(raster, output_dir, zoom):
    """Generate an XYZ tile pyramid ({z}/{x}/{y}.png) with a Leaflet preview."""
    res = generate_xyz_tiles(raster, output_dir, *zoom)
    click.echo(f"{res.written} tiles written ({res.skipped_empty} empty skipped), "
               f"zoom {res.zooms[0]}-{res.zooms[1]}. Open {Path(output_dir) / 'preview.html'} "
               "via a local server: python -m http.server")


@main.command("s3-upload")
@click.argument("local_dir", type=click.Path(exists=True, file_okay=False))
@click.option("--bucket", required=True)
@click.option("--prefix", default="", help="Key prefix, e.g. deliveries/2026-09")
@click.option("--dry-run", is_flag=True, help="List uploads without calling AWS")
def s3_upload(local_dir, bucket, prefix, dry_run):
    """Upload a results folder to S3 (credentials from the standard AWS chain)."""
    keys = upload_directory(local_dir, bucket, prefix, dry_run=dry_run)
    click.echo(f"{'Would upload' if dry_run else 'Uploaded'} {len(keys)} files")


@main.command()
@click.argument("path", type=click.Path(exists=True, dir_okay=False))
def info(path):
    """Print CRS, bounds, size and schema of a dataset as JSON."""
    click.echo(json.dumps(describe(path), indent=2, default=str))


@main.command()
def formats():
    """List supported output vector formats."""
    for key, (driver, ext) in sorted(VECTOR_FORMATS.items()):
        click.echo(f"{key:8} {ext:9} {driver}")


if __name__ == "__main__":
    main()
