#!/usr/bin/env bash
# Set up the AAAIR public tools on a fresh Ubuntu 24.04 Nectar VM:
#   - WP2 Open Healthcare Dataset Explorer
#   - WP6.4 Course Finder prototypes
#
#   curl -fsSL https://raw.githubusercontent.com/gnanabharathy/AAAIR/main/deploy/nectar-setup.sh -o nectar-setup.sh
#   sudo EXPLORER_ADDRESS=explorer.<your-zone>.cloud.edu.au \
#        COURSES_ADDRESS=courses.<your-zone>.cloud.edu.au \
#        bash nectar-setup.sh
#
# Leave the addresses unset to serve plain HTTP on the instance's IP address:
# the explorer on port 80 and the course finder on port 8081.
# Re-running the script updates to the latest commit and rebuilds.
#
# See DEPLOY.md for the security group and DNS steps that must come first.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/gnanabharathy/AAAIR.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/aaair}"
EXPLORER_ADDRESS="${EXPLORER_ADDRESS:-:80}"
COURSES_ADDRESS="${COURSES_ADDRESS:-:8081}"

if [ "$(id -u)" -ne 0 ]; then
  echo "Run as root (sudo)." >&2
  exit 1
fi

echo "==> Installing Docker, Compose and BuildKit from the Ubuntu archive"
# Ubuntu's own packages are kept patched by unattended-upgrades, which Nectar's
# Ubuntu images enable by default.
export DEBIAN_FRONTEND=noninteractive
apt-get update -q
apt-get install -y -q docker.io docker-compose-v2 docker-buildx git
systemctl enable --now docker

echo "==> Fetching from $REPO_URL ($REPO_BRANCH)"
# Sparse, shallow clone: only the folders the tools are built from.
if [ -d "$INSTALL_DIR/.git" ]; then
  git -C "$INSTALL_DIR" sparse-checkout set deploy WP2 WP6
  git -C "$INSTALL_DIR" fetch --depth 1 origin "$REPO_BRANCH"
  git -C "$INSTALL_DIR" checkout -q -B "$REPO_BRANCH" FETCH_HEAD
else
  git clone -q --depth 1 --filter=blob:none --sparse --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR"
  git -C "$INSTALL_DIR" sparse-checkout set deploy WP2 WP6
fi

echo "==> Building and starting"
echo "    explorer: $EXPLORER_ADDRESS"
echo "    courses:  $COURSES_ADDRESS"
cd "$INSTALL_DIR/deploy"
# Persist the addresses so a reboot, or a later `docker compose up`, keeps them.
printf 'EXPLORER_ADDRESS=%s\nCOURSES_ADDRESS=%s\n' "$EXPLORER_ADDRESS" "$COURSES_ADDRESS" > .env
docker compose up -d --build

echo "==> Waiting for both services to report healthy"
healthy() {
  [ "$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q "$1")" 2>/dev/null)" = "healthy" ]
}
for _ in $(seq 1 40); do
  healthy explorer && healthy courses && break
  sleep 3
done
docker compose ps

failed=0
for svc in explorer courses; do
  if ! healthy "$svc"; then
    echo "$svc did not become healthy. Check: docker compose logs $svc" >&2
    failed=1
  fi
done
[ "$failed" -eq 0 ] || exit 1

url() {
  case "$1" in
    :80) echo "http://<this instance's public IP>/" ;;
    :*)  echo "http://<this instance's public IP>$1/" ;;
    *)   echo "https://$1/" ;;
  esac
}
echo "Done."
echo "  Dataset Explorer: $(url "$EXPLORER_ADDRESS")"
echo "  Course Finder:    $(url "$COURSES_ADDRESS")"
echo "The first HTTPS visit may take a few seconds while certificates are issued."
