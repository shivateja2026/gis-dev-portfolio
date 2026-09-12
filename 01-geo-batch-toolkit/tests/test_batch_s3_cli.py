import json
from pathlib import Path

import boto3
import pytest
from click.testing import CliRunner
from moto import mock_aws

from geobatch.batch import run_batch
from geobatch.cli import main
from geobatch.formats import discover
from geobatch.s3 import upload_directory
from geobatch.vector import convert_vector


def test_batch_continues_after_bad_file(vector_dir, tmp_path):
    (vector_dir / "corrupt.geojson").write_text("{not valid json")
    files = discover(vector_dir, "vector")
    out = tmp_path / "out"
    results = run_batch(convert_vector, files, out, out_dir=out, fmt="gpkg")
    status = {Path(r.source).name: r.status for r in results}
    assert status["corrupt.geojson"] == "error"
    assert sum(s == "ok" for s in status.values()) == 3
    report = json.loads((out / "run_report.json").read_text())
    assert report["total"] == 4 and report["failed"] == 1
    assert (out / "run_report.csv").exists()


def test_batch_parallel(vector_dir, tmp_path):
    files = discover(vector_dir, "vector")
    out = tmp_path / "out"
    results = run_batch(convert_vector, files, out, workers=2, out_dir=out, fmt="fgb")
    assert all(r.status == "ok" for r in results)


@pytest.fixture
def s3_bucket(monkeypatch):
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "testing")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "testing")
    monkeypatch.setenv("AWS_DEFAULT_REGION", "ap-south-1")
    with mock_aws():
        client = boto3.client("s3", region_name="ap-south-1")
        client.create_bucket(Bucket="bmgt-deliveries",
                             CreateBucketConfiguration={"LocationConstraint": "ap-south-1"})
        yield client


def test_s3_upload_keys_and_content_types(tmp_path, s3_bucket):
    d = tmp_path / "deliver"
    (d / "9" / "380").mkdir(parents=True)
    (d / "9" / "380" / "230.png").write_bytes(b"png")
    (d / "zones.geojson").write_text("{}")
    keys = upload_directory(d, "bmgt-deliveries", "client-a/2026-09", client=s3_bucket)
    assert sorted(keys) == ["client-a/2026-09/9/380/230.png", "client-a/2026-09/zones.geojson"]
    head = s3_bucket.head_object(Bucket="bmgt-deliveries", Key="client-a/2026-09/zones.geojson")
    assert head["ContentType"] == "application/geo+json"


def test_s3_dry_run_makes_no_calls(tmp_path):
    d = tmp_path / "deliver"
    d.mkdir()
    (d / "a.tif").write_bytes(b"x")
    assert upload_directory(d, "any-bucket", dry_run=True) == ["a.tif"]


def test_cli_vector_convert_and_info(vector_dir, tmp_path):
    runner = CliRunner()
    out = tmp_path / "cli_out"
    r = runner.invoke(main, ["vector-convert", str(vector_dir), str(out), "--to", "tab",
                             "--crs", "EPSG:32644"])
    assert r.exit_code == 0, r.output
    assert "3/3 succeeded" in r.output
    r = runner.invoke(main, ["info", str(out / "sites.tab")])
    assert r.exit_code == 0 and '"features": 50' in r.output


def test_cli_bad_bbox():
    r = CliRunner().invoke(main, ["vector-convert", ".", "out", "--to", "gpkg", "--bbox", "1,2,3"])
    assert r.exit_code != 0 and "minx,miny,maxx,maxy" in r.output
