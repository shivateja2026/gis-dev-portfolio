"""Vector conversion, reprojection and clipping."""

from __future__ import annotations

import logging
from collections.abc import Callable
from pathlib import Path

import geopandas as gpd
import pyogrio
from shapely.geometry import box

from .formats import VECTOR_FORMATS, WGS84_ONLY, dataset_size_bytes

log = logging.getLogger(__name__)

BBox = tuple[float, float, float, float]

# Above this size, convert_vector reads/writes in batches instead of loading the
# whole dataset into memory at once (see convert_vector_chunked).
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


def convert_vector_chunked(
    src: Path,
    out_path: Path,
    fmt: str,
    target_crs: str | None,
    bbox: BBox | None,
    mask: gpd.GeoDataFrame | None,
    chunk_size: int,
    progress_cb: Callable[[int, int], None] | None,
) -> Path:
    """Read/transform/write in batches so the whole dataset never sits in memory at once."""
    _clear_existing_output(out_path)
    total = pyogrio.read_info(src)["features"]
    wrote_any = False
    for offset in range(0, total, chunk_size):
        gdf = gpd.read_file(src, engine="pyogrio", skip_features=offset, max_features=chunk_size)
        gdf = transform_vector(gdf, target_crs, bbox, mask)
        if not gdf.empty:
            write_vector(gdf, out_path, fmt, mode="a" if wrote_any else "w")
            wrote_any = True
        if progress_cb:
            progress_cb(min(offset + chunk_size, total), total)
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
    if dataset_size_bytes(src) >= chunk_threshold:
        return convert_vector_chunked(
            src, out_path, fmt, target_crs, bbox, mask, chunk_size, progress_cb
        )
    gdf = transform_vector(read_vector(src), target_crs, bbox, mask)
    if gdf.empty:
        log.warning("%s: no features left after clipping", src.name)
    return write_vector(gdf, out_path, fmt)
