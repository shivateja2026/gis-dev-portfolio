import json

import rasterio
from PIL import Image

from geobatch.raster import convert_raster, is_cog
from geobatch.tiles import generate_xyz_tiles


def test_raster_to_cog(raster_path, tmp_path):
    out = convert_raster(raster_path, tmp_path / "out")
    assert is_cog(out)
    with rasterio.open(out) as ds:
        assert ds.nodata == -9999


def test_raster_reproject_and_clip(raster_path, tmp_path):
    out = convert_raster(raster_path, tmp_path / "out", target_crs="EPSG:32644",
                         bbox=(260_000, 2_160_000, 280_000, 2_180_000), resampling="bilinear")
    with rasterio.open(out) as ds:
        assert ds.crs.to_epsg() == 32644
        assert ds.bounds.left >= 259_000 and ds.bounds.right <= 281_000
    assert is_cog(out)


def test_xyz_tiles(raster_path, tmp_path):
    out = tmp_path / "tiles"
    res = generate_xyz_tiles(raster_path, out, 9, 11)
    assert res.written > 0
    pngs = list(out.rglob("*.png"))
    assert len(pngs) == res.written
    img = Image.open(pngs[0])
    assert img.size == (256, 256) and img.mode == "RGBA"
    meta = json.loads((out / "metadata.json").read_text())
    assert meta["minzoom"] == 9 and meta["maxzoom"] == 11
    assert (out / "preview.html").exists()
    assert {p.parts[-3] for p in pngs} == {"9", "10", "11"}
