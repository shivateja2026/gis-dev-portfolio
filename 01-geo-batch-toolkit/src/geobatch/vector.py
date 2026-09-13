"""Vector conversion, reprojection and clipping."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pyogrio
from shapely.geometry import box

from .formats import VECTOR_FORMATS, WGS84_ONLY, dataset_size_bytes

log = logging.getLogger(__name__)

BBox = tuple[float, float, float, float]

# convert_vector always reads/transforms in batches of this size (so progress can be
# reported); above this source size it also *writes* incrementally, so the whole
# dataset never sits in memory at once. FlatGeobuf is exempt from incremental writes
# (see convert_vector_batched) regardless of size.
CHUNK_THRESHOLD_BYTES = 5 * 1024**3
CHUNK_SIZE_FEATURES = 200_000


def read_vector(path: str | Path) -> gpd.GeoDataFrame:
    return gpd.read_file(path, engine="pyogrio")


def transform_vector(
    gdf: gpd.GeoDataFrame,
    target_crs: str | None = None,
    bbox: BBox | None = None,
    mask: gpd.GeoDataFrame | None = None,
) -> gpd.GeoDataFrame:
    """Reproject then clip. ``bbox`` is interpreted in the *output* CRS."""
    if target_crs:
        if gdf.crs is None:
            raise ValueError("Source has no CRS defined; cannot reproject. Assign a CRS first.")
        gdf = gdf.to_crs(target_crs)
    if bbox is not None:
        gdf = gdf.clip(box(*bbox))
    if mask is not None:
        gdf = gdf.clip(mask.to_crs(gdf.crs) if mask.crs != gdf.crs else mask)
    return gdf


def _clear_existing_output(out_path: Path) -> None:
    """Remove an old dataset (and sidecars) so reruns are idempotent."""
    if out_path.exists():
        for sidecar in out_path.parent.glob(out_path.stem + ".*"):
            sidecar.unlink()


def write_vector(gdf: gpd.GeoDataFrame, out_path: Path, fmt: str, mode: str = "w") -> Path:
    driver, _ = VECTOR_FORMATS[fmt]
    if fmt in WGS84_ONLY and gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        log.warning("%s requires EPSG:4326; reprojecting %s from %s", fmt, out_path.name, gdf.crs)
        gdf = gdf.to_crs(4326)
    if fmt == "shp":
        long_fields = [c for c in gdf.columns if c != "geometry" and len(c) > 10]
        if long_fields:
            log.warning("Shapefile truncates field names >10 chars: %s", long_fields)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if mode == "w":
        _clear_existing_output(out_path)
    gdf.to_file(out_path, driver=driver, engine="pyogrio", mode=mode)
    return out_path


def convert_vector_batched(
    src: Path,
    out_path: Path,
    fmt: str,
    target_crs: str | None,
    bbox: BBox | None,
    mask: gpd.GeoDataFrame | None,
    chunk_size: int,
    progress_cb: Callable[[int, int], None] | None,
    stream_write: bool,
) -> Path:
    """Read/transform in batches (so progress can be reported on any size of input).

    ``stream_write`` writes each batch as it's read, so the whole dataset never sits in
    memory at once. When ``False`` (FlatGeobuf, or anything under the chunk threshold),
    batches are accumulated and written once at the end instead - same memory profile
    as a single-shot conversion, just read in pieces so progress is visible.
    """
    _clear_existing_output(out_path)
    total = pyogrio.read_info(src)["features"]
    pending = []
    wrote_any = False
    for offset in range(0, total, chunk_size):
        gdf = gpd.read_file(src, engine="pyogrio", skip_features=offset, max_features=chunk_size)
        gdf = transform_vector(gdf, target_crs, bbox, mask)
        if not gdf.empty:
            if stream_write:
                write_vector(gdf, out_path, fmt, mode="a" if wrote_any else "w")
                wrote_any = True
            else:
                pending.append(gdf)
        if progress_cb:
            progress_cb(min(offset + chunk_size, total), total)
    if pending:
        write_vector(pd.concat(pending, ignore_index=True), out_path, fmt)
        wrote_any = True
    if not wrote_any:
        log.warning("%s: no features left after clipping", src.name)
    return out_path


def convert_vector(
    src: str | Path,
    out_dir: str | Path,
    fmt: str,
    target_crs: str | None = None,
    bbox: BBox | None = None,
    mask_path: str | Path | None = None,
    chunk_threshold: int = CHUNK_THRESHOLD_BYTES,
    chunk_size: int = CHUNK_SIZE_FEATURES,
    progress_cb: Callable[[int, int], None] | None = None,
) -> Path:
    """Convert one vector dataset. Returns the output path."""
    if fmt not in VECTOR_FORMATS:
        raise ValueError(f"Unsupported output format '{fmt}'. Choose from {sorted(VECTOR_FORMATS)}")
    src = Path(src)
    mask = read_vector(mask_path) if mask_path else None
    out_path = Path(out_dir) / f"{src.stem}{VECTOR_FORMATS[fmt][1]}"
    size = dataset_size_bytes(src)
    stream_write = fmt != "fgb" and size >= chunk_threshold
    if fmt == "fgb" and size >= chunk_threshold:
        log.info("FlatGeobuf doesn't support efficient chunked appends; converting %s "
                 "(%.1fGB) in a single pass instead", src.name, size / 1024**3)
    return convert_vector_batched(
        src, out_path, fmt, target_crs, bbox, mask, chunk_size, progress_cb, stream_write
    )
