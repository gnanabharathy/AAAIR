# WP2 Dataset Explorer container image

Builds the Open Healthcare Dataset Explorer as a container. To run it on Nectar
alongside the other AAAIR tools, see [`deploy/DEPLOY.md`](../../deploy/DEPLOY.md)
at the repository root.

| File | Purpose |
|------|---------|
| `Dockerfile` | Multi-stage build with `WP2/` as the build context |
| `Dockerfile.dockerignore` | Allowlist of the only WP2 files that enter the image |
| `requirements.txt` | Pinned Python dependencies |
| `app/api.py`, `app/schema.html` | Hosting versions of the WP2 originals, used only by the image |

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

## Hosting versions of WP2 files

The original `WP2/api.py` and `WP2/schema.html` are unchanged. Hosting needs
modified versions, so these live in `deploy/app/` and the Dockerfile copies them
over the originals inside the image only.

If the originals change, apply the same change to the copies in `deploy/app/`
(or re-derive the copies from the new originals), then rebuild. Otherwise the
website will keep serving the old behaviour. To see the differences:

```bash
cd WP2
diff api.py deploy/app/api.py
diff schema.html deploy/app/schema.html
```

**`app/schema.html`:**

- Had `http://localhost:8765` hardcoded in its three API calls. Hosted
  anywhere, the page would have called port 8765 on the *visitor's own
  computer* and failed. The calls are now relative (`/api/...`).
- Now shows PHIDU's required attribution above every PHIDU table. PHIDU content
  is licensed CC BY-NC-SA 3.0 AU, and the explorer previously republished it
  without attribution. The wording follows PHIDU's form for modified material,
  since the explorer reshapes the source tables. When the spreadsheets in
  `phidu_data/` are re-downloaded, update `PHIDU_ACCESSED` (and
  `PHIDU_ATLAS` if the year changes) at the top of the PHIDU code.

**`app/api.py`:**

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
