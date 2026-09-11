"""Raster reprojection, clipping and Cloud-Optimized GeoTIFF output."""

from __future__ import annotations

import logging
from pathlib import Path

import rasterio
import rasterio.shutil
from rasterio.enums import Resampling
from rasterio.io import MemoryFile
from rasterio.mask import mask as rio_mask
from rasterio.vrt import WarpedVRT
from shapely.geometry import box, mapping

log = logging.getLogger(__name__)

BBox = tuple[float, float, float, float]

RESAMPLING = {m.name: m for m in (Resampling.nearest, Resampling.bilinear, Resampling.cubic)}


def convert_raster(
    src: str | Path,
    out_dir: str | Path,
    target_crs: str | None = None,
    bbox: BBox | None = None,
    cog: bool = True,
    resampling: str = "nearest",
    compress: str = "DEFLATE",
) -> Path:
    """Reproject (optional), clip (optional, bbox in output CRS) and write COG or GeoTIFF.

    Use ``nearest`` for categorical rasters (LULC classes) and ``bilinear``/``cubic``
    for continuous data (DEM, reflectance).
    """
    src = Path(src)
    out_path = Path(out_dir) / f"{src.stem}.tif"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    driver = "COG" if cog else "GTiff"

    with rasterio.open(src) as ds:
        if target_crs and ds.crs is None:
            raise ValueError(f"{src.name} has no CRS; cannot reproject.")
        source = (
            WarpedVRT(ds, crs=target_crs, resampling=RESAMPLING[resampling]) if target_crs else ds
        )
        try:
            if bbox is None:
                rasterio.shutil.copy(source, out_path, driver=driver, compress=compress)
            else:
                data, transform = rio_mask(source, [mapping(box(*bbox))], crop=True)
                profile = source.profile.copy()
                profile.update(
                    driver="GTiff", height=data.shape[1], width=data.shape[2], transform=transform
                )
                profile.pop("blockxsize", None)
                profile.pop("blockysize", None)
                profile.pop("tiled", None)
                with MemoryFile() as mem, mem.open(**profile) as tmp:
                    tmp.write(data)
                    rasterio.shutil.copy(tmp, out_path, driver=driver, compress=compress)
        finally:
            if source is not ds:
                source.close()
    return out_path


def is_cog(path: str | Path) -> bool:
    with rasterio.open(path) as ds:
        return ds.tags(ns="IMAGE_STRUCTURE").get("LAYOUT") == "COG"
