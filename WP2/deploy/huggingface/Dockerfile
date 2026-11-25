# Open Healthcare Dataset Explorer (AAAIR WP2): Hugging Face Docker Space
#
# This is the Space's Dockerfile. It is not built from the WP2 folder.
# deploy/huggingface/build_spaces.py stages the Space repository with the data
# already compressed and trimmed (the job that stage 1 of WP2/deploy/Dockerfile
# does), so the Space stays small and builds quickly.
#
# Differences from WP2/deploy/Dockerfile:
#   - no data stage: app/ arrives ready to serve
#   - runs as UID 1000, which Hugging Face uses for Space containers
#   - listens on 7860, the Hugging Face default (also set as app_port in README.md)

FROM python:3.11-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PORT=7860

WORKDIR /srv

# Installed from /tmp, outside /srv, because api.py serves every file in /srv.
COPY requirements.txt /tmp/requirements.txt
RUN pip install --no-cache-dir -r /tmp/requirements.txt \
 && rm /tmp/requirements.txt

RUN useradd --create-home --uid 1000 explorer

# App code and data stay root-owned. Only phidu_data is writable, so api.py
# can fetch a spreadsheet that schema.json references but the Space lacks.
COPY app/index.html app/app.js app/data.js app/style.css app/api.py app/schema.html app/schema.json.gz ./
COPY app/dqd/ dqd/
COPY --chown=explorer:explorer app/phidu_data/ phidu_data/

USER explorer

EXPOSE 7860

CMD ["sh", "-c", "exec gunicorn api:app \
      --bind 0.0.0.0:${PORT} \
      --workers 2 \
      --threads 4 \
      --timeout 120 \
      --preload \
      --access-logfile -"]
