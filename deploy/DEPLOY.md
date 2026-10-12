# Deploying the AAAIR public tools on Nectar

This folder runs two AAAIR tools as public websites on one Nectar Research Cloud
virtual machine (VM). Visitors need no account and no software; they open a link.

| Tool | Work package | What it is | Image |
|------|--------------|------------|-------|
| Open Healthcare Dataset Explorer | WP2 | Flask app: dataset metadata and OMOP data quality reports for NHANES, PHIDU and PTB-XL | [`WP2/deploy/`](../WP2/deploy/README.md) |
| Course Finder | WP6.4 | Three static prototype pages that help health researchers find analytics and AI training | [`WP6/deploy/`](../WP6/deploy/README.md) |

Neither tool holds a database, credentials or user data. Everything they show is
already public.

## What is in this folder

| File | Purpose |
|------|---------|
| `docker-compose.yml` | Builds both images and runs them behind Caddy |
| `Caddyfile` | Routes each address to its tool; handles HTTPS, compression and security headers |
| `nectar-setup.sh` | One-command install and update on a fresh Ubuntu VM |

## How it fits together

```
                              ┌──▶ explorer (gunicorn, internal port 8765)
visitor ──HTTPS──▶ Caddy ─────┤
               (80, 443)      └──▶ courses  (static files, internal port 8080)
```

Caddy routes by hostname, for example `explorer.<your-zone>` and
`courses.<your-zone>`. It obtains and renews a Let's Encrypt certificate for each
name on its own. Neither tool is reachable from outside except through Caddy.

## Deploy on Nectar

### 1. Check the allocation

You need a Nectar project allocation. Before deploying, confirm with the ARDC
Nectar team that running public-facing websites is within your allocation's
terms.

Also settle where these tools should live. The AAAIR README says WP7 targets
deployment into NeCTAR-backed virtual research environments (VREs). VREs
normally require users to log in, which is the opposite of an open public link.
If the tools should sit inside a VRE, raise that with the ARDC VRE Cloud Service
team before following this guide.

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
| 8081 | TCP | Your institution's IP range only | Temporary: the course finder before DNS is set up. Remove once HTTPS works. |

Do not open ports 8765 or 8080. Nothing needs to reach the tools directly.

### 3. Launch the instance

- **Image:** Ubuntu 24.04 LTS (the setup script assumes Ubuntu's package names)
- **Size:** 2 vCPU and 4 GB RAM is ample. The explorer uses about 210 MB at
  rest and the course finder a few MB; the headroom covers image builds and
  PHIDU requests, which parse spreadsheets of up to 69 MB. Choose the matching
  flavour in the Nectar dashboard, as flavour names vary.
- **Disk:** 30 GB covers Ubuntu, Docker, the checkout (about 1.7 GB) and both
  images.
- **Security group:** the one from step 2.
- **Key pair:** yours, for SSH.

If the instance is on a private network, attach a floating IP to give it a
public address
([Nectar tutorial: attaching a floating IP](https://tutorials.rc.nectar.org.au/advanced-networking/07-attach-a-floating-ip)).
Floating IPs come from your project's quota.

### 4. Point DNS names at it

HTTPS needs a DNS name for each tool. Nectar creates a DNS zone automatically
for new projects and for allocations being renewed. The zone name is based on
your project name and ends in `.cloud.edu.au`
([Nectar tutorial: DNS in a nutshell](https://tutorials.rc.nectar.org.au/dns/02-in-a-nutshell);
[Nectar Support: DNS service](https://support.ehelp.edu.au/support/solutions/articles/6000201311-nectar-dns-service)).

In the Nectar dashboard, add two `A` records in that zone, both pointing at the
instance's public IP, for example `explorer.<your-zone>` and
`courses.<your-zone>`. Wait until both resolve before step 5:

```bash
dig +short explorer.<your-zone>
dig +short courses.<your-zone>
```

You can skip this step to check the VM over plain HTTP on the bare IP address:
the explorer on port 80 and the course finder on port 8081. Use HTTPS for
anything shared.

### 5. Run the setup script

SSH in, then:

```bash
curl -fsSL https://raw.githubusercontent.com/gnanabharathy/AAAIR/main/deploy/nectar-setup.sh -o nectar-setup.sh
sudo EXPLORER_ADDRESS=explorer.<your-zone> \
     COURSES_ADDRESS=courses.<your-zone> \
     bash nectar-setup.sh
```

The script installs Docker from the Ubuntu archive, makes a shallow sparse clone
of `deploy/`, `WP2/` and `WP6/` into `/opt/aaair`, builds both images and starts
everything. It waits for both health checks before reporting success. All
containers restart automatically after a reboot.

The first build takes a few minutes, mostly gzipping about 1.1 GB of WP2 data
quality reports.

## Operating it

**Update to the latest commit.** Re-run the setup script with the same
addresses. It fetches, rebuilds and restarts.

**Logs.**

```bash
cd /opt/aaair/deploy
docker compose logs -f explorer   # explorer app and access log
docker compose logs -f courses    # course finder
docker compose logs -f caddy      # HTTPS and certificate events
```

**Health.** `https://explorer.<your-zone>/healthz` returns the number of
datasets loaded. `https://courses.<your-zone>/healthz` returns `ok`.

**What you are responsible for.** A Nectar VM is yours to maintain. Ubuntu's
unattended-upgrades applies security patches, including to Docker, but you
should still reboot after kernel updates and occasionally rebuild to pick up
patched base images. Caddy renews certificates by itself. There is no data to
back up: everything is rebuilt from the repository, apart from Caddy's
certificate store in the `caddy_data` volume.

## Adding another tool

Give the tool its own `deploy/Dockerfile` with an allowlist
`Dockerfile.dockerignore`, add a service to `docker-compose.yml`, add an address
block to `Caddyfile`, and add its folder to the `sparse-checkout` line in
`nectar-setup.sh`.
