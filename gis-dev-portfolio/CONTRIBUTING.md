# Contributing & Configuration Management

## Branching strategy (GitHub Flow + release tags)
- `main` is always releasable and protected: no direct pushes, PR + passing CI required.
- Work on short-lived branches named `<type>/<module>-<short-desc>`:
  - `feat/geo-batch-toolkit-mapinfo`
  - `fix/qgis-plugin-crs-dialog`
  - `docs/raster-tiling-runbook`
- One logical change per PR. Link the issue (`Closes #12`).

## Commit messages (Conventional Commits)
```
feat(geo-batch-toolkit): add MapInfo TAB writer
fix(raster): handle nodata edges in tile generation
docs(readme): update JD coverage matrix
test(s3): cover dry-run upload
```

## Versioning & releases
- Each module is versioned independently with SemVer.
- Release = update `CHANGELOG.md` → merge PR → tag `<module>-vX.Y.Z` → GitHub Release.

## Code review checklist
- [ ] CI green (lint + tests)
- [ ] New behaviour has a test
- [ ] No hard-coded paths, credentials or keys (use env vars / `.env`, never committed)
- [ ] CRS handling explicit (no silent reprojection)
- [ ] README / docs updated
- [ ] Honesty table still accurate

## Local setup
```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e "01-geo-batch-toolkit[dev]"
pytest 01-geo-batch-toolkit
```
