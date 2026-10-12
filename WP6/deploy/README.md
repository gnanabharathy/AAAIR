# WP6.4 Course Finder container image

Serves the three WP6.4 Course Finder prototypes as a website. To run it on
Nectar alongside the other AAAIR tools, see
[`deploy/DEPLOY.md`](../../deploy/DEPLOY.md) at the repository root.

| File | Purpose |
|------|---------|
| `Dockerfile` | Static file server on Caddy, with `WP6/` as the build context |
| `Dockerfile.dockerignore` | Allowlist: the three prototypes and this folder's own files |
| `Caddyfile` | Internal server configuration: plain HTTP on port 8080, plus `/healthz` |
| `index.html` | Landing page linking the prototypes |

The prototypes are self-contained HTML pages with their course data embedded,
so there is no application code and nothing to compile. The image adds a few MB
to the Caddy base image and runs as an unprivileged user. HTTPS and compression
are handled by the shared Caddy in front.

| Path | Prototype |
|------|-----------|
| `/` | Landing page |
| `/Wizard_prototype1.html` | Guided needs assessment |
| `/dashboard_prototype2.html` | Course dashboard, with enrolment status |
| `/dashboard_prototype1.html` | Course dashboard, earlier version |

## Run it locally

```bash
cd WP6
docker build -f deploy/Dockerfile -t aaair-courses .
docker run -p 8080:8080 aaair-courses
```

Then open <http://localhost:8080>.

## Difference between the two dashboards

`dashboard_prototype2.html` adds enrolment status to each course card ("Enrol
anytime", a scheduled start date, or "Enrolment closed") and hides one-time
events that have already passed unless the user filters for them. Otherwise the
two are the same. This is read from the HTML; the landing page lists version 2
first for that reason.

## Updating the prototypes

The image serves the HTML files committed in `WP6.4/`, so replacing a file and
rebuilding is enough. `dashboard_prototype2.qmd` cannot currently be
re-rendered from this repository: it reads
`../01_data/6.4_cleaned_extraction_data.csv`, which is not committed (see the
WP6 README).
