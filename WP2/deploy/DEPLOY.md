# Deploying the Open Healthcare Dataset Explorer on Nectar

This folder packages the WP2 explorer as a container and runs it on a Nectar
Research Cloud virtual machine (VM) as a public website. Visitors need no
account and no software; they open a link.

The explorer holds no database, no credentials and no user data. Every dataset
it shows is already public (NHANES, PHIDU, PTB-XL). That keeps it low-risk to
host.

## What is in this folder

| File | Purpose |
|------|---------|
| `Dockerfile` | Builds the image, with `WP2/` as the build context |
| `Dockerfile.dockerignore` | Allowlist of the only WP2 files that enter the image |
| `requirements.txt` | Pinned Python dependencies |
| `docker-compose.yml` | Runs the explorer behind Caddy, which handles HTTPS |
| `Caddyfile` | Caddy configuration: HTTPS, compression, security headers |
| `nectar-setup.sh` | One-command install and update on a fresh Ubuntu VM |

## How it fits together

```
visitor ──HTTPS──▶ Caddy (ports 80, 443) ──▶ explorer (gunicorn, port 8765, internal only)
```

Caddy obtains and renews a Let's Encrypt certificate on its own once a DNS name
points at the VM. The explorer container is not reachable from outside except
through Caddy.

The image is self-contained. It includes all 298 DQD reports and the 12 PHIDU
spreadsheets that `schema.json` references, so it makes no outbound requests at
runtime.

## Deploy on Nectar

### 1. Check the allocation

You need a Nectar project allocation. Before deploying, confirm with the ARDC
Nectar team that running a public-facing website is within your allocation's
terms.

Also settle the question of where this should live. The AAAIR README says WP7
targets deployment into NeCTAR-backed virtual research environments (VREs).
VREs normally require users to log in, which is the opposite of an open public
link. If the explorer should sit inside a VRE, raise that with the ARDC VRE
Cloud Service team before following this guide.

### 2. Create a security group

Nectar security groups deny all inbound traffic by default
([Nectar Support: security groups](https://support.ehelp.edu.au/support/solutions/articles/6000151135-using-security-groups)).
Create one with these ingress rules:

| Port | Protocol | Source | Why |
|------|----------|--------|-----|
| 22 | TCP | Your institution's IP range only | SSH for administration |
| 80 | TCP | `0.0.0.0/0` | HTTP, and Let's Encrypt validation |
| 443 | TCP | `0.0.0.0/0` | HTTPS |
| 443 | UDP | `0.0.0.0/0` | HTTP/3 (optional) |

Do not open port 8765. Nothing needs to reach the explorer directly.

### 3. Launch the instance

- **Image:** Ubuntu 24.04 LTS (the setup script assumes Ubuntu's package names)
- **Size:** 2 vCPU and 4 GB RAM is ample. The running app uses about 210 MB;
  the headroom covers the image build and PHIDU requests, which parse
  spreadsheets of up to 69 MB. Choose the matching flavour in the Nectar
  dashboard, as flavour names vary.
- **Disk:** 30 GB covers Ubuntu, Docker, the WP2 checkout (about 1.6 GB) and the
  built image.
- **Security group:** the one from step 2.
- **Key pair:** yours, for SSH.

If the instance is on a private network, attach a floating IP to give it a
public address
([Nectar tutorial: attaching a floating IP](https://tutorials.rc.nectar.org.au/advanced-networking/07-attach-a-floating-ip)).
Floating IPs come from your project's quota.

### 4. Point a DNS name at it

HTTPS needs a DNS name. Nectar creates a DNS zone automatically for new projects
and for allocations being renewed. The zone name is based on your project name
and ends in `.cloud.edu.au`
([Nectar tutorial: DNS in a nutshell](https://tutorials.rc.nectar.org.au/dns/02-in-a-nutshell);
[Nectar Support: DNS service](https://support.ehelp.edu.au/support/solutions/articles/6000201311-nectar-dns-service)).

In the Nectar dashboard, add an `A` record in that zone, for example
`explorer.<your-zone>`, pointing at the instance's public IP. Wait until it
resolves before step 5:

```bash
dig +short explorer.<your-zone>
```

You can skip this step to run over plain HTTP on the bare IP address. That is
fine for a quick check, but use HTTPS for anything shared.

### 5. Run the setup script

SSH in, then:

```bash
curl -fsSL https://raw.githubusercontent.com/gnanabharathy/AAAIR/main/WP2/deploy/nectar-setup.sh -o nectar-setup.sh
sudo SITE_ADDRESS=explorer.<your-zone> bash nectar-setup.sh
```

The script installs Docker from the Ubuntu archive, makes a shallow sparse clone
of `WP2/` into `/opt/aaair`, builds the image and starts both containers. It
waits for the explorer's health check before reporting success. Both containers
restart automatically after a reboot.

The first build takes a few minutes, mostly gzipping about 1.1 GB of DQD
reports.

## Operating it

**Update to the latest commit.** Re-run the setup script with the same
`SITE_ADDRESS`. It fetches, rebuilds and restarts.

**Logs.**

```bash
cd /opt/aaair/WP2/deploy
docker compose logs -f explorer   # app and access log
docker compose logs -f caddy      # HTTPS and certificate events
```

**Health.** `curl https://explorer.<your-zone>/healthz` returns the number of
datasets loaded, a quick check that the schema loaded correctly.

**What you are responsible for.** A Nectar VM is yours to maintain. Ubuntu's
unattended-upgrades applies security patches, including to Docker, but you
should still reboot after kernel updates and occasionally rebuild to pick up a
patched Python base image. Caddy renews certificates by itself. There is no
data to back up: everything is rebuilt from the repository, apart from Caddy's
certificate store in the `caddy_data` volume.

## Run it locally

```bash
cd WP2
docker build -f deploy/Dockerfile -t aaair-explorer .
docker run -p 8765:8765 aaair-explorer
```

Then open <http://localhost:8765>. Or, without Docker, the original instructions
in `WP2/README.md` still work unchanged.

## Changes made to WP2 for hosting

Two WP2 files changed. Both changes are backward compatible: `python api.py`
from a plain checkout behaves as before.

**`schema.html`** had `http://localhost:8765` hardcoded in its three API calls.
Hosted anywhere, the page would have called port 8765 on the *visitor's own
computer* and failed. The calls are now relative (`/api/...`).

**`api.py`:**

- Reads `.json` or `.json.gz`, so the image can ship compressed data (about
  1.1 GB of JSON becomes about 40 MB).
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
