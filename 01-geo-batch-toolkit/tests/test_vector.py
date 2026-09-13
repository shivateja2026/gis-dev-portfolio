import geopandas as gpd
import pytest

from geobatch.formats import discover
from geobatch.vector import convert_vector


def test_discover_ignores_sidecars(vector_dir):
    names = {p.name for p in discover(vector_dir, "vector")}
    assert names == {"sites.shp", "zones.geojson", "legacy_sites.tab"}


def test_shp_to_gpkg_preserves_features_and_attributes(vector_dir, tmp_path):
    out = convert_vector(vector_dir / "sites.shp", tmp_path / "out", "gpkg")
    gdf = gpd.read_file(out)
    assert out.suffix == ".gpkg"
    assert len(gdf) == 50
    assert {"site_id", "name", "elev_m"} <= set(gdf.columns)


@pytest.mark.parametrize("fmt", ["tab", "mif"])
def test_mapinfo_round_trip(vector_dir, tmp_path, fmt):
    out = convert_vector(vector_dir / "sites.shp", tmp_path / "out", fmt)
    gdf = gpd.read_file(out)
    assert len(gdf) == 50
    assert gdf.crs is not None


def test_read_mapinfo_input(vector_dir, tmp_path):
    out = convert_vector(vector_dir / "legacy_sites.tab", tmp_path / "out", "geojson")
    assert len(gpd.read_file(out)) == 50


def test_reprojection_to_utm(vector_dir, tmp_path):
    out = convert_vector(vector_dir / "sites.shp", tmp_path / "out", "gpkg",
                         target_crs="EPSG:32644")
    gdf = gpd.read_file(out)
    assert gdf.crs.to_epsg() == 32644
    assert gdf.total_bounds[0] > 100_000  # metres, not degrees


def test_bbox_clip_reduces_features(vector_dir, tmp_path, points_gdf):
    minx, miny, maxx, maxy = points_gdf.total_bounds
    half = (minx, miny, (minx + maxx) / 2, maxy)
    out = convert_vector(vector_dir / "sites.shp", tmp_path / "out", "gpkg", bbox=half)
    n = len(gpd.read_file(out))
    assert 0 < n < 50


def test_kml_forces_wgs84(vector_dir, tmp_path):
    out = convert_vector(vector_dir / "zones.geojson", tmp_path / "out", "kml",
                         target_crs="EPSG:32644")
    assert gpd.read_file(out).crs.to_epsg() == 4326


def test_rerun_is_idempotent(vector_dir, tmp_path):
    for _ in range(2):
        out = convert_vector(vector_dir / "sites.shp", tmp_path / "out", "shp")
    assert len(gpd.read_file(out)) == 50


def test_chunked_path_matches_single_shot(vector_dir, tmp_path):
    calls = []
    chunked = convert_vector(vector_dir / "sites.shp", tmp_path / "chunked", "gpkg",
                             target_crs="EPSG:32644", chunk_threshold=0, chunk_size=7,
                             progress_cb=lambda done, total: calls.append((done, total)))
    whole = convert_vector(vector_dir / "sites.shp", tmp_path / "whole", "gpkg",
                           target_crs="EPSG:32644")
    chunked_gdf, whole_gdf = gpd.read_file(chunked), gpd.read_file(whole)
    assert len(chunked_gdf) == len(whole_gdf) == 50
    assert chunked_gdf.total_bounds == pytest.approx(whole_gdf.total_bounds)
    assert calls[-1] == (50, 50)


def test_unknown_format_rejected(vector_dir, tmp_path):
    with pytest.raises(ValueError, match="Unsupported"):
        convert_vector(vector_dir / "sites.shp", tmp_path, "dwg")
