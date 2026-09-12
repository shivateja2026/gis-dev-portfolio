"""Vector conversion, reprojection and clipping."""

from __future__ import annotations

import logging
from pathlib import Path

import geopandas as gpd
from shapely.geometry import box

from .formats import VECTOR_FORMATS, WGS84_ONLY

log = logging.getLogger(__name__)

BBox = tuple[float, float, float, float]


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


def write_vector(gdf: gpd.GeoDataFrame, out_path: Path, fmt: str) -> Path:
    driver, _ = VECTOR_FORMATS[fmt]
    if fmt in WGS84_ONLY and gdf.crs is not None and gdf.crs.to_epsg() != 4326:
        log.warning("%s requires EPSG:4326; reprojecting %s from %s", fmt, out_path.name, gdf.crs)
        gdf = gdf.to_crs(4326)
    if fmt == "shp":
        long_fields = [c for c in gdf.columns if c != "geometry" and len(c) > 10]
        if long_fields:
            log.warning("Shapefile truncates field names >10 chars: %s", long_fields)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    if out_path.exists():
        # Remove old dataset (and sidecars) so reruns are idempotent.
        for sidecar in out_path.parent.glob(out_path.stem + ".*"):
            sidecar.unlink()
    gdf.to_file(out_path, driver=driver, engine="pyogrio")
    return out_path


def convert_vector(
    src: str | Path,
    out_dir: str | Path,
    fmt: str,
    target_crs: str | None = None,
    bbox: BBox | None = None,
    mask_path: str | Path | None = None,
) -> Path:
    """Convert one vector dataset. Returns the output path."""
    if fmt not in VECTOR_FORMATS:
        raise ValueError(f"Unsupported output format '{fmt}'. Choose from {sorted(VECTOR_FORMATS)}")
    src = Path(src)
    gdf = read_vector(src)
    mask = read_vector(mask_path) if mask_path else None
    gdf = transform_vector(gdf, target_crs, bbox, mask)
    if gdf.empty:
        log.warning("%s: no features left after clipping", src.name)
    out_path = Path(out_dir) / f"{src.stem}{VECTOR_FORMATS[fmt][1]}"
    return write_vector(gdf, out_path, fmt)
