"""Supported formats and file discovery rules."""

from __future__ import annotations

from pathlib import Path

# key -> (OGR driver name, output extension)
VECTOR_FORMATS: dict[str, tuple[str, str]] = {
    "shp": ("ESRI Shapefile", ".shp"),
    "gpkg": ("GPKG", ".gpkg"),
    "geojson": ("GeoJSON", ".geojson"),
    "fgb": ("FlatGeobuf", ".fgb"),
    "kml": ("KML", ".kml"),
    "tab": ("MapInfo File", ".tab"),  # MapInfo native (.tab/.dat/.map/.id)
    "mif": ("MapInfo File", ".mif"),  # MapInfo interchange (.mif/.mid)
}

# Selecting only required extensions.
# Sidecar files (.dbf, .shx, .prj, .dat, .map, .id, .mid) are deliberately excluded.
VECTOR_INPUT_EXTS = {".shp", ".gpkg", ".geojson", ".fgb", ".kml", ".tab", ".mif"}

RASTER_INPUT_EXTS = {".tif", ".tiff", ".img", ".jp2"}

# These file formats specifications fixes the CRS to WGS84 lon/lat.
WGS84_ONLY = {"kml", "geojson"}


def discover(input_dir: str | Path, kind: str, recursive: bool = True) -> list[Path]:
    """Return primary dataset files of a given kind ("vector" or "raster"), sorted."""
    exts = VECTOR_INPUT_EXTS if kind == "vector" else RASTER_INPUT_EXTS
    root = Path(input_dir)
    if not root.is_dir():
        raise NotADirectoryError(f"Input directory not found: {root}")
    pattern = "**/*" if recursive else "*"
    return sorted(p for p in root.glob(pattern) if p.is_file() and p.suffix.lower() in exts)


def dataset_size_bytes(path: str | Path) -> int:
    """Total size of a dataset's primary file plus any sidecars sharing its stem.

    A Shapefile's ``.dbf`` is often larger than the ``.shp`` itself, so the primary
    file alone understates a dataset's real size.
    """
    path = Path(path)
    return sum(p.stat().st_size for p in path.parent.glob(path.stem + ".*"))
