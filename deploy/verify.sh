#!/usr/bin/env bash
# Check a Nectar deployment from the outside. Run from any computer, not the VM,
# so the checks see what a visitor sees.
#
# Before DNS (plain HTTP on the instance's public IP):
#   bash verify.sh --ip 203.0.113.10
#
# After DNS (HTTPS on each name):
#   bash verify.sh explorer.<your-zone>.cloud.edu.au courses.<your-zone>.cloud.edu.au
#
# Each failed check names the step in DEPLOY.md that most likely needs fixing.
set -uo pipefail

pass=0
fail=0
ok()  { printf '  PASS  %s\n' "$1"; pass=$((pass + 1)); }
bad() { printf '  FAIL  %s\n        -> %s\n' "$1" "$2"; fail=$((fail + 1)); }

port_open() {  # host port
  timeout 5 bash -c "exec 3<>/dev/tcp/$1/$2" 2>/dev/null
}

code() {  # url -> HTTP status, or 000 if unreachable
  curl -s -o /dev/null -w '%{http_code}' --max-time 15 "$1"
}

check_closed() {  # host port
  if port_open "$1" "$2"; then
    bad "port $2 is closed to the internet" "close it in the security group (step 2); only Caddy should be reachable"
  else
    ok "port $2 is closed to the internet"
  fi
}

check_not_served() {  # base-url path
  local c
  c=$(code "$1$2")
  if [ "$c" = "404" ]; then ok "$2 is not published"; else bad "$2 is not published (got HTTP $c)" "check the image's Dockerfile.dockerignore allowlist"; fi
}

if [ "${1:-}" = "--ip" ]; then
  ip="${2:?usage: verify.sh --ip <public-ip>}"
  echo "Checking $ip (plain HTTP, before DNS)"

  if port_open "$ip" 80; then ok "port 80 is reachable"; else bad "port 80 is reachable" "open TCP 80 in the security group (step 2), and check the floating IP is attached (step 3)"; fi
  if port_open "$ip" 8081; then ok "port 8081 is reachable"; else bad "port 8081 is reachable" "open TCP 8081 to your IP range in the security group (step 2)"; fi

  body=$(curl -s --max-time 15 "http://$ip/healthz")
  case "$body" in *'"status":"ok"'*) ok "explorer is healthy ($body)" ;; *) bad "explorer is healthy" "on the VM run: cd /opt/aaair/deploy && docker compose logs explorer" ;; esac
  if [ "$(curl -s --max-time 15 "http://$ip:8081/healthz")" = "ok" ]; then
    ok "course finder is healthy"
  else
    bad "course finder is healthy" "on the VM run: cd /opt/aaair/deploy && docker compose logs courses"
  fi

  check_not_served "http://$ip" /docker-compose.yml
  check_not_served "http://$ip:8081" /WP6.4_Report.docx
  check_closed "$ip" 8765
  check_closed "$ip" 8080
else
  explorer="${1:?usage: verify.sh <explorer-name> <courses-name>  or  verify.sh --ip <public-ip>}"
  courses="${2:?usage: verify.sh <explorer-name> <courses-name>}"
  echo "Checking https://$explorer and https://$courses"

  ip=""
  for name in "$explorer" "$courses"; do
    addr=$(getent ahostsv4 "$name" 2>/dev/null | awk 'NR==1{print $1}')
    if [ -n "$addr" ]; then ok "$name resolves to $addr"; ip=${ip:-$addr}; else bad "$name resolves" "add an A record for $name in the Nectar DNS zone (step 4), then allow time to propagate"; fi
  done
  [ -z "$ip" ] && { echo; echo "No name resolves yet; stopping. $fail failed."; exit 1; }

  if port_open "$ip" 443; then ok "port 443 is reachable"; else bad "port 443 is reachable" "open TCP 443 in the security group (step 2)"; fi
  if port_open "$ip" 80; then ok "port 80 is reachable"; else bad "port 80 is reachable" "open TCP 80 in the security group (step 2); Let's Encrypt needs it to issue certificates"; fi

  for name in "$explorer" "$courses"; do
    c=$(code "https://$name/healthz")
    if [ "$c" = "200" ]; then
      ok "https://$name has a valid certificate and is healthy"
    elif curl -sk -o /dev/null --max-time 15 "https://$name/healthz"; then
      bad "https://$name has a valid certificate" "certificate not issued yet; on the VM run: cd /opt/aaair/deploy && docker compose logs caddy"
    else
      bad "https://$name responds" "check the setup script was run with this name (step 5)"
    fi
    loc=$(curl -s -o /dev/null -w '%{redirect_url}' --max-time 15 "http://$name/")
    case "$loc" in https://*) ok "http://$name redirects to HTTPS" ;; *) bad "http://$name redirects to HTTPS" "check the address passed to the setup script is the bare name, without :80" ;; esac
  done

  check_not_served "https://$explorer" /docker-compose.yml
  check_not_served "https://$explorer" /requirements.txt
  check_not_served "https://$courses" /WP6.4_Report.docx
  check_closed "$ip" 8765
  check_closed "$ip" 8080
  if port_open "$ip" 8081; then
    bad "port 8081 is closed now that HTTPS works" "remove the temporary 8081 rule from the security group (step 2)"
  else
    ok "port 8081 is closed now that HTTPS works"
  fi
fi

echo
echo "$pass passed, $fail failed."
[ "$fail" -eq 0 ]
