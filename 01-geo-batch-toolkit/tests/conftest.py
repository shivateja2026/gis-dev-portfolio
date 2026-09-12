"""Synthetic test data: no downloads, runs anywhere."""

import geopandas as gpd
import numpy as np
import pytest
import rasterio
from rasterio.transform import from_origin
from shapely.geometry import Point, box

LON0, LAT0 = 78.53, 19.66  # Adilabad, Telangana


@pytest.fixture
def points_gdf():
    rng = np.random.default_rng(42)
    lons = LON0 + rng.uniform(-0.2, 0.2, 50)
    lats = LAT0 + rng.uniform(-0.2, 0.2, 50)
    return gpd.GeoDataFrame(
        {"site_id": range(50), "name": [f"site_{i}" for i in range(50)],
         "elev_m": rng.uniform(200, 400, 50).round(1)},
        geometry=[Point(x, y) for x, y in zip(lons, lats, strict=True)],
        crs="EPSG:4326",
    )


@pytest.fixture
def polygons_gdf():
    cells = [box(LON0 + i * 0.1, LAT0 + j * 0.1, LON0 + (i + 1) * 0.1, LAT0 + (j + 1) * 0.1)
             for i in range(3) for j in range(3)]
    return gpd.GeoDataFrame({"zone": [f"Z{i}" for i in range(9)]}, geometry=cells,
                            crs="EPSG:4326")


@pytest.fixture
def vector_dir(tmp_path, points_gdf, polygons_gdf):
    d = tmp_path / "vin"
    d.mkdir()
    points_gdf.to_file(d / "sites.shp", engine="pyogrio")
    polygons_gdf.to_file(d / "zones.geojson", driver="GeoJSON", engine="pyogrio")
    points_gdf.to_file(d / "legacy_sites.tab", driver="MapInfo File", engine="pyogrio")
    return d


@pytest.fixture
def raster_path(tmp_path):
    """0.4 x 0.4 degree float32 DEM-like raster with a nodata strip."""
    d = tmp_path / "rin"
    d.mkdir()
    path = d / "dem.tif"
    h = w = 200
    yy, xx = np.mgrid[0:h, 0:w]
    data = (250 + xx * 0.5 + yy * 0.3).astype("float32")
    data[:, :10] = -9999
    transform = from_origin(LON0 - 0.2, LAT0 + 0.2, 0.002, 0.002)
    with rasterio.open(path, "w", driver="GTiff", height=h, width=w, count=1, dtype="float32",
                       crs="EPSG:4326", transform=transform, nodata=-9999) as ds:
        ds.write(data, 1)
    return path
