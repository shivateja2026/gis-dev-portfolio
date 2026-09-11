"""Deliver outputs to AWS S3."""

from __future__ import annotations

import logging
import mimetypes
from pathlib import Path

log = logging.getLogger(__name__)

EXTRA_TYPES = {
    ".geojson": "application/geo+json",
    ".gpkg": "application/geopackage+sqlite3",
    ".fgb": "application/octet-stream",
    ".tif": "image/tiff",
    ".json": "application/json",
    ".png": "image/png",
}


def content_type(path: Path) -> str:
    return EXTRA_TYPES.get(path.suffix.lower()) or (
        mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    )


def upload_directory(
    local_dir: str | Path,
    bucket: str,
    prefix: str = "",
    dry_run: bool = False,
    client=None,
) -> list[str]:
    """Upload every file under ``local_dir`` to ``s3://bucket/prefix/...``.

    Credentials come from the standard AWS chain (env vars, ~/.aws/credentials, IAM role);
    nothing is hard-coded. ``dry_run`` lists what would be uploaded without any AWS call.
    """
    root = Path(local_dir)
    if not root.is_dir():
        raise NotADirectoryError(root)
    prefix = prefix.strip("/")
    files = sorted(p for p in root.rglob("*") if p.is_file())
    keys = []
    if not dry_run and client is None:
        import boto3

        client = boto3.client("s3")
    for f in files:
        rel = f.relative_to(root).as_posix()
        key = f"{prefix}/{rel}" if prefix else rel
        keys.append(key)
        if dry_run:
            log.info("[dry-run] %s -> s3://%s/%s", f, bucket, key)
            continue
        client.upload_file(str(f), bucket, key, ExtraArgs={"ContentType": content_type(f)})
    log.info("%s %d files to s3://%s/%s", "Would upload" if dry_run else "Uploaded",
             len(keys), bucket, prefix)
    return keys
