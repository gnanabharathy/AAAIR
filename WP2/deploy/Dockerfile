# Open Healthcare Dataset Explorer (AAAIR WP2)
#
# Build from the WP2 directory, which is the build context:
#
#   cd WP2
#   docker build -f deploy/Dockerfile -t aaair-explorer .
#   docker run -p 8765:8765 aaair-explorer
#
# Only the files allowlisted in deploy/Dockerfile.dockerignore reach the build,
# so the ETL scripts, raw CSVs and the OMOP database compose file never enter
# the image. This matters because api.py serves every file in its directory.

# ---- Stage 1: compress the data -------------------------------------------
FROM python:3.11-slim AS data

WORKDIR /build
COPY schema.json ./
COPY dqd/raw/ dqd/raw/
COPY phidu_data/ phidu_data/

# gzip the JSON (about 1.1 GB raw down to about 40 MB; api.py reads .gz
# transparently) and keep only the PHIDU spreadsheets that schema.json
# actually references, so the image never has to download them at runtime.
RUN gzip -9 schema.json \
 && gzip -9 dqd/raw/*.json \
 && python - <<'PY'
import gzip, json, os
schema = json.load(gzip.open('schema.json.gz', 'rt', encoding='utf-8'))
keep = {v['url'].rsplit('/', 1)[-1] for v in schema.values() if v.get('source') == 'PHIDU'}
for name in os.listdir('phidu_data'):
    if name not in keep:
        os.remove(os.path.join('phidu_data', name))
missing = keep - set(os.listdir('phidu_data'))
print(f'PHIDU spreadsheets kept: {len(keep) - len(missing)}, missing: {sorted(missing)}')
PY

# ---- Stage 2: runtime -----------------------------------------------------
FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=8765

WORKDIR /srv

# curl is used only by HEALTHCHECK.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl \
 && rm -rf /var/lib/apt/lists/*

# Installed from /tmp, outside /srv, because api.py would otherwise serve it
# and publish the exact dependency versions.
COPY deploy/requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

RUN useradd --create-home --uid 10001 explorer

# App code and data stay root-owned, so the app cannot modify itself. Only
# phidu_data is writable, so api.py can fetch a spreadsheet if a future
# schema.json references one that was not baked in. Setting ownership in the
# COPY, rather than a later chown, avoids storing the 214 MB twice.
COPY api.py index.html schema.html app.js data.js style.css ./
COPY --from=data /build/schema.json.gz ./
COPY --from=data /build/dqd/ dqd/
COPY --from=data --chown=explorer:explorer /build/phidu_data/ phidu_data/

USER explorer

EXPOSE 8765

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
  CMD curl -fsS "http://127.0.0.1:${PORT}/healthz" || exit 1

# --preload loads the schema once before forking, so workers share it
# copy-on-write instead of each holding a copy.
#
# JSON form so Docker passes signals straight through; the inner `exec` makes
# gunicorn PID 1, so SIGTERM stops it cleanly. The shell is only there to
# expand ${PORT}.
CMD ["sh", "-c", "exec gunicorn api:app \
      --bind 0.0.0.0:${PORT} \
      --workers 2 \
      --threads 4 \
      --timeout 120 \
      --preload \
      --access-logfile -"]
