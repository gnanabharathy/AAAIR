# AAAIR WP6.4 Course Finder prototypes
#
# Build from the WP6 directory, which is the build context:
#
#   cd WP6
#   docker build -f deploy/Dockerfile -t aaair-courses .
#   docker run -p 8080:8080 aaair-courses
#
# The three prototypes are self-contained HTML pages with their course data
# embedded, so this is a plain static file server with no application code.
# HTTPS is handled by the shared Caddy in front (deploy/ at the repo root).

FROM caddy:2

COPY ["06 Resources & Training (WP6)/WP6.4/Wizard_prototype1.html", \
      "06 Resources & Training (WP6)/WP6.4/dashboard_prototype1.html", \
      "06 Resources & Training (WP6)/WP6.4/dashboard_prototype2.html", \
      "/srv/"]
COPY deploy/index.html /srv/index.html
COPY deploy/Caddyfile /etc/caddy/Caddyfile

# Run as an unprivileged user. Caddy keeps its state under /data and /config
# even with TLS off, so those must be writable; the site files stay root-owned.
RUN chown -R 65534:65534 /data /config
USER 65534

EXPOSE 8080

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget -qO- http://127.0.0.1:8080/healthz || exit 1
