#!/usr/bin/env bash
# Set up the Open Healthcare Dataset Explorer on a fresh Ubuntu 24.04 Nectar VM.
#
#   curl -fsSL https://raw.githubusercontent.com/gnanabharathy/AAAIR/main/WP2/deploy/nectar-setup.sh -o nectar-setup.sh
#   sudo SITE_ADDRESS=explorer.<your-project-zone>.cloud.edu.au bash nectar-setup.sh
#
# Leave SITE_ADDRESS unset to serve plain HTTP on the instance's IP address.
# Re-running the script updates to the latest commit and rebuilds.
#
# See DEPLOY.md for the security group and DNS steps that must come first.
set -euo pipefail

REPO_URL="${REPO_URL:-https://github.com/gnanabharathy/AAAIR.git}"
REPO_BRANCH="${REPO_BRANCH:-main}"
INSTALL_DIR="${INSTALL_DIR:-/opt/aaair}"
SITE_ADDRESS="${SITE_ADDRESS:-:80}"

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

echo "==> Fetching WP2 from $REPO_URL ($REPO_BRANCH)"
# Sparse, shallow clone: only WP2, only the latest commit.
if [ -d "$INSTALL_DIR/.git" ]; then
  git -C "$INSTALL_DIR" fetch --depth 1 origin "$REPO_BRANCH"
  git -C "$INSTALL_DIR" checkout -q -B "$REPO_BRANCH" FETCH_HEAD
else
  git clone -q --depth 1 --filter=blob:none --sparse --branch "$REPO_BRANCH" "$REPO_URL" "$INSTALL_DIR"
  git -C "$INSTALL_DIR" sparse-checkout set WP2
fi

echo "==> Building and starting (SITE_ADDRESS=$SITE_ADDRESS)"
cd "$INSTALL_DIR/WP2/deploy"
# Persist the address so a reboot, or a later `docker compose up`, keeps it.
echo "SITE_ADDRESS=$SITE_ADDRESS" > .env
docker compose up -d --build

echo "==> Waiting for the explorer to report healthy"
for _ in $(seq 1 40); do
  status=$(docker inspect -f '{{.State.Health.Status}}' "$(docker compose ps -q explorer)" 2>/dev/null || true)
  [ "$status" = "healthy" ] && break
  sleep 3
done
docker compose ps

if [ "$status" != "healthy" ]; then
  echo "Explorer did not become healthy. Check: docker compose logs explorer" >&2
  exit 1
fi

if [ "$SITE_ADDRESS" = ":80" ]; then
  echo "Done. Open http://<this instance's public IP>/"
else
  echo "Done. Open https://$SITE_ADDRESS/ (the first visit may take a few seconds while the certificate is issued)."
fi
