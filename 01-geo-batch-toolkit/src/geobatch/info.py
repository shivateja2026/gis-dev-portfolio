"""Quick inspection of a vector or raster dataset."""

from __future__ import annotations

from pathlib import Path

import pyogrio
import rasterio

from .formats import RASTER_INPUT_EXTS


def describe(path: str | Path) -> dict:
    p = Path(path)
    if p.suffix.lower() in RASTER_INPUT_EXTS:
        with rasterio.open(p) as ds:
            return {
                "type": "raster",
                "driver": ds.driver,
                "crs": ds.crs.to_string() if ds.crs else None,
                "size": [ds.width, ds.height],
                "bands": ds.count,
                "dtype": ds.dtypes[0],
                "nodata": ds.nodata,
                "resolution": list(ds.res),
                "bounds": list(ds.bounds),
                "layout": ds.tags(ns="IMAGE_STRUCTURE").get("LAYOUT", "GTiff"),
            }
    meta = pyogrio.read_info(p)
    return {
        "type": "vector",
        "driver": meta.get("driver"),
        "crs": meta.get("crs"),
        "features": meta.get("features"),
        "geometry_type": meta.get("geometry_type"),
        "fields": list(meta.get("fields", [])),
        "bounds": list(meta["total_bounds"]) if meta.get("total_bounds") is not None else None,
    }
