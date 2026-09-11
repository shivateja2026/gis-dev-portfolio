"""End-to-end demo: generate sample data, then run every geobatch command.

Run from the module folder:  python examples/demo.py
Works on Windows, macOS and Linux. Output lands in ./out (git-ignored).
"""

import subprocess
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, box

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "out"
VIN, RIN = OUT / "input_vector", OUT / "input_raster"


def make_samples() -> None:
    VIN.mkdir(parents=True, exist_ok=True)
    RIN.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(7)
    lon0, lat0 = 78.53, 19.66
    pts = gpd.GeoDataFrame(
        {"site_id": range(200), "category": rng.choice(["school", "clinic", "office"], 200)},
        geometry=[Point(lon0 + dx, lat0 + dy) for dx, dy in rng.uniform(-0.3, 0.3, (200, 2))],
        crs="EPSG:4326",
    )
    grid = gpd.GeoDataFrame(
        {"cell": range(16)},
        geometry=[box(lon0 - 0.3 + i * 0.15, lat0 - 0.3 + j * 0.15,
                      lon0 - 0.15 + i * 0.15, lat0 - 0.15 + j * 0.15)
                  for i in range(4) for j in range(4)],
        crs="EPSG:4326",
    )
    pts.to_file(VIN / "facilities.shp", engine="pyogrio")
    grid.to_file(VIN / "grid.geojson", driver="GeoJSON", engine="pyogrio")
    pts.to_file(VIN / "legacy_facilities.tab", driver="MapInfo File", engine="pyogrio")

    h = w = 600
    yy, xx = np.mgrid[0:h, 0:w]
    dem = (300 + 80 * np.sin(xx / 60) * np.cos(yy / 80) + yy * 0.1).astype("float32")
    with rasterio.open(RIN / "dem.tif", "w", driver="GTiff", height=h, width=w, count=1,
                       dtype="float32", crs="EPSG:4326", nodata=-9999,
                       transform=from_origin(lon0 - 0.3, lat0 + 0.3, 0.001, 0.001)) as ds:
        ds.write(dem, 1)


def run(*args: str) -> None:
    cmd = [sys.executable, "-m", "geobatch.cli", *args]
    print("\n$ geobatch " + " ".join(args))
    subprocess.run(cmd, check=True)


if __name__ == "__main__":
    make_samples()
    run("formats")
    run("vector-convert", str(VIN), str(OUT / "gpkg_utm"), "--to", "gpkg", "--crs", "EPSG:32644")
    run("vector-convert", str(VIN), str(OUT / "mapinfo"), "--to", "tab")
    run("raster-convert", str(RIN), str(OUT / "cog"), "--crs", "EPSG:32644",
        "--resampling", "bilinear")
    run("info", str(OUT / "cog" / "dem.tif"))
    run("tiles", str(RIN / "dem.tif"), str(OUT / "tiles"), "--zoom", "9-13")
    run("s3-upload", str(OUT / "tiles"), "--bucket", "bmgt-deliveries",
        "--prefix", "demo/dem", "--dry-run")
    print(f"\nDone. Preview tiles: cd {OUT / 'tiles'} && python -m http.server 8000"
          "  → open http://localhost:8000/preview.html")
