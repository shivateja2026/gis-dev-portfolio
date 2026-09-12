"""XYZ (slippy-map) tile pyramid generation from a raster."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path

import mercantile
import numpy as np
import rasterio
from PIL import Image
from rasterio.enums import Resampling
from rasterio.transform import from_bounds
from rasterio.warp import reproject, transform_bounds

log = logging.getLogger(__name__)

WEB_MERCATOR = "EPSG:3857"
MAX_LAT = 85.05112878


@dataclass
class TileResult:
    written: int
    skipped_empty: int
    zooms: tuple[int, int]
    bounds_wgs84: tuple[float, float, float, float]


def _scale_to_uint8(arr: np.ndarray, vmin: float, vmax: float) -> np.ndarray:
    if vmax <= vmin:
        return np.zeros_like(arr, dtype=np.uint8)
    scaled = (arr.astype("float64") - vmin) / (vmax - vmin) * 255.0
    return np.clip(scaled, 0, 255).astype(np.uint8)


def _stats(ds: rasterio.DatasetReader, bands: list[int]) -> tuple[float, float]:
    """Global min/max from an overview-level read, so every tile shares one stretch."""
    factor = max(1, max(ds.width, ds.height) // 1024)
    data = ds.read(
        bands,
        out_shape=(len(bands), max(1, ds.height // factor), max(1, ds.width // factor)),
        masked=True,
    )
    if data.count() == 0:
        return 0.0, 1.0
    return float(data.min()), float(data.max())


def generate_xyz_tiles(
    src: str | Path,
    out_dir: str | Path,
    min_zoom: int,
    max_zoom: int,
    tile_size: int = 256,
    resampling: str = "bilinear",
) -> TileResult:
    """Write ``{z}/{x}/{y}.png`` tiles plus ``metadata.json`` and a Leaflet ``preview.html``.

    1-band rasters become greyscale; 3+ band rasters use bands 1-3 as RGB. Nodata and
    areas outside the raster are transparent. Fully transparent tiles are not written.
    """
    if min_zoom > max_zoom:
        raise ValueError("min_zoom must be <= max_zoom")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    rs = Resampling[resampling]
    written = skipped = 0

    with rasterio.open(src) as ds:
        if ds.crs is None:
            raise ValueError("Raster has no CRS; cannot tile.")
        bands = [1, 2, 3] if ds.count >= 3 else [1]
        vmin, vmax = _stats(ds, bands)
        west, south, east, north = transform_bounds(ds.crs, "EPSG:4326", *ds.bounds)
        south, north = max(south, -MAX_LAT), min(north, MAX_LAT)
        nodata = ds.nodata

        for tile in mercantile.tiles(west, south, east, north, range(min_zoom, max_zoom + 1)):
            xb = mercantile.xy_bounds(tile)
            dst_transform = from_bounds(xb.left, xb.bottom, xb.right, xb.top, tile_size, tile_size)
            # NaN marks "no data": outside the raster footprint or source nodata.
            dest = np.full((len(bands), tile_size, tile_size), np.nan, dtype="float64")
            reproject(
                source=rasterio.band(ds, bands),
                destination=dest,
                src_transform=ds.transform,
                src_crs=ds.crs,
                src_nodata=nodata,
                dst_transform=dst_transform,
                dst_crs=WEB_MERCATOR,
                dst_nodata=np.nan,
                resampling=rs,
            )
            valid = ~np.isnan(dest).any(axis=0)
            if not valid.any():
                skipped += 1
                continue

            rgb = _scale_to_uint8(np.nan_to_num(dest, nan=vmin), vmin, vmax)
            alpha = (valid * 255).astype(np.uint8)
            if len(bands) == 1:
                img = Image.fromarray(np.stack([rgb[0]] * 3 + [alpha], axis=-1), "RGBA")
            else:
                img = Image.fromarray(np.dstack([rgb[0], rgb[1], rgb[2], alpha]), "RGBA")

            tile_path = out / str(tile.z) / str(tile.x) / f"{tile.y}.png"
            tile_path.parent.mkdir(parents=True, exist_ok=True)
            img.save(tile_path, optimize=True)
            written += 1

    bounds = (west, south, east, north)
    meta = {
        "tilejson": "3.0.0",
        "name": Path(src).stem,
        "scheme": "xyz",
        "tiles": ["{z}/{x}/{y}.png"],
        "minzoom": min_zoom,
        "maxzoom": max_zoom,
        "bounds": list(bounds),
        "center": [(west + east) / 2, (south + north) / 2, min_zoom],
        "stretch": {"min": vmin, "max": vmax},
    }
    (out / "metadata.json").write_text(json.dumps(meta, indent=2))
    (out / "preview.html").write_text(_preview_html(meta))
    log.info("Tiles: %d written, %d empty skipped", written, skipped)
    return TileResult(written, skipped, (min_zoom, max_zoom), bounds)


def _preview_html(meta: dict) -> str:
    lon, lat, z = meta["center"]
    return f"""<!doctype html>
<html><head><meta charset="utf-8"><title>{meta['name']} tiles</title>
<link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css"/>
<script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
<style>html,body,#map{{height:100%;margin:0}}</style></head>
<body><div id="map"></div><script>
const map = L.map('map').setView([{lat}, {lon}], {z});
L.tileLayer('https://tile.openstreetmap.org/{{z}}/{{x}}/{{y}}.png',
  {{attribution: '&copy; OpenStreetMap contributors'}}).addTo(map);
L.tileLayer('{{z}}/{{x}}/{{y}}.png', {{minZoom:{meta['minzoom']}, maxZoom:{meta['maxzoom']},
  opacity:0.8}}).addTo(map);
</script></body></html>
"""
