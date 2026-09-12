"""Parallel batch runner with a per-file run report."""

from __future__ import annotations

import csv
import json
import logging
import time
from collections.abc import Callable
from concurrent.futures import ProcessPoolExecutor, as_completed
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

log = logging.getLogger(__name__)


@dataclass
class FileResult:
    source: str
    status: str  # "ok" | "error"
    output: str | None
    seconds: float
    error: str | None = None


def _run_one(func: Callable, src: Path, kwargs: dict) -> FileResult:
    t0 = time.perf_counter()
    try:
        out = func(src, **kwargs)
        return FileResult(str(src), "ok", str(out), round(time.perf_counter() - t0, 3))
    except Exception as exc:  # one bad file must not stop the batch
        return FileResult(str(src), "error", None, round(time.perf_counter() - t0, 3),
                          f"{type(exc).__name__}: {exc}")


def run_batch(
    func: Callable,
    files: list[Path],
    report_dir: str | Path,
    workers: int = 1,
    **kwargs,
) -> list[FileResult]:
    """Apply ``func(src, **kwargs)`` to every file; write ``run_report.json`` and ``.csv``."""
    results: list[FileResult] = []
    if workers <= 1:
        for f in files:
            r = _run_one(func, f, kwargs)
            _log_result(r)
            results.append(r)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            futures = [pool.submit(_run_one, func, f, kwargs) for f in files]
            for fut in as_completed(futures):
                r = fut.result()
                _log_result(r)
                results.append(r)
    results.sort(key=lambda r: r.source)
    write_report(results, report_dir)
    return results


def _log_result(r: FileResult) -> None:
    if r.status == "ok":
        log.info("OK    %s -> %s (%.2fs)", r.source, r.output, r.seconds)
    else:
        log.error("FAIL  %s: %s", r.source, r.error)


def write_report(results: list[FileResult], report_dir: str | Path) -> Path:
    d = Path(report_dir)
    d.mkdir(parents=True, exist_ok=True)
    summary = {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "total": len(results),
        "ok": sum(r.status == "ok" for r in results),
        "failed": sum(r.status == "error" for r in results),
        "total_seconds": round(sum(r.seconds for r in results), 3),
        "files": [asdict(r) for r in results],
    }
    path = d / "run_report.json"
    path.write_text(json.dumps(summary, indent=2))
    with open(d / "run_report.csv", "w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(FileResult.__dataclass_fields__))
        w.writeheader()
        w.writerows(asdict(r) for r in results)
    return path
