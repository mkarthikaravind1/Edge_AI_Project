#!/usr/bin/env bash
# Create a private CA and a server certificate for the Mosquitto TLS listener (works on the Pi and in Git Bash).
#   bash docker/mosquitto/make_certs.sh [extra-hostname-or-ip ...]
# -> docker/mosquitto/certs/{ca.crt, ca.key, server.crt, server.key}   (git-ignored; never commit *.key)
set -euo pipefail
export MSYS_NO_PATHCONV=1                      # Git Bash: stop "/CN=..." being turned into a Windows path
cd "$(dirname "$0")"
mkdir -p certs && cd certs

DAYS=825
SAN="DNS:localhost,DNS:mosquitto,DNS:pi-karthik,DNS:pi-karthik.local,IP:127.0.0.1"
for extra in "$@"; do
  if [[ "$extra" =~ ^[0-9.]+$ ]]; then SAN="$SAN,IP:$extra"; else SAN="$SAN,DNS:$extra"; fi
done

openssl req -x509 -new -nodes -newkey rsa:2048 -days "$DAYS" -sha256 \
  -keyout ca.key -out ca.crt -subj "/CN=edge-inspection-ca/O=Karthik Aravind M"
openssl req -new -nodes -newkey rsa:2048 -keyout server.key -out server.csr -subj "/CN=pi-karthik"
printf "subjectAltName=%s\nextendedKeyUsage=serverAuth\nkeyUsage=digitalSignature,keyEncipherment\n" "$SAN" > server.ext
openssl x509 -req -in server.csr -CA ca.crt -CAkey ca.key -CAcreateserial -days "$DAYS" -sha256 \
  -extfile server.ext -out server.crt
rm -f server.csr server.ext ca.srl
chmod 644 ca.crt server.crt server.key   # the broker runs as user 1883 inside the container and must read the key
chmod 600 ca.key
openssl verify -CAfile ca.crt server.crt
echo "SAN: $SAN"
