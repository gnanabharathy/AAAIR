# WP2 Dataset Explorer container image

Builds the Open Healthcare Dataset Explorer as a container. To run it on Nectar
alongside the other AAAIR tools, see [`deploy/DEPLOY.md`](../../deploy/DEPLOY.md)
at the repository root.

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build with `WP2/` as the build context |
| `Dockerfile.dockerignore` | Allowlist of the only WP2 files that enter the image |
| `requirements.txt` | Pinned Python dependencies |

The image is self-contained, at about 560 MB. The build gzips `schema.json` and
all DQD reports (about 1.1 GB of JSON becomes about 40 MB) and keeps only the 12
PHIDU spreadsheets that `schema.json` references, so the app makes no outbound
requests at runtime. It runs as a non-root user that cannot modify the app code.

## Run it locally

```bash
cd WP2
docker build -f deploy/Dockerfile -t aaair-explorer .
docker run -p 8765:8765 aaair-explorer
```

Then open <http://localhost:8765>. Or, without Docker, the original instructions
in [`WP2/README.md`](../README.md) still work unchanged.

## Changes made to WP2 for hosting

Two WP2 files changed. Both changes are backward compatible: `python api.py`
from a plain checkout behaves as before.

**`schema.html`** had `http://localhost:8765` hardcoded in its three API calls.
Hosted anywhere, the page would have called port 8765 on the *visitor's own
computer* and failed. The calls are now relative (`/api/...`).

**`api.py`:**

- Reads `.json` or `.json.gz`, so the image can ship compressed data.
- Adds a `/healthz` endpoint for the container health check.
- Re-enables TLS certificate checking when downloading PHIDU spreadsheets. It
  had been switched off, but the PHIDU site's certificate validates normally,
  so this was unnecessary and left the download open to interception.
- `python api.py` now reads `PORT`, `HOST` and `FLASK_DEBUG` from the
  environment. Defaults are port 8765 on `127.0.0.1`, as before, but with the
  Flask debugger **off** unless `FLASK_DEBUG=1` is set. The debugger allows
  code execution from the browser, so it should not be on by default.

## Known limitations

- `api.py` serves any file in its own directory. The image is safe because the
  allowlist in `Dockerfile.dockerignore` admits only the explorer's own files.
  Anything added to that allowlist becomes publicly downloadable.
- `app.js` references a `PROXY` variable that is never defined. That code path
  never runs, so it causes no error, but it is dead code.
- `WP2/README.md` tells users to clone
  `github.com/jennyVVei/open-healthcare-dataset-explorer-quality-tool`, which is
  not publicly accessible. The copy in this repository is the one that works.
