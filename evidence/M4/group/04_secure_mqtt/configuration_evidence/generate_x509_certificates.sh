#!/bin/bash
# Production X.509 Certificate Generation for Edge MQTT (Reference Utility)
set -e
mkdir -p certs && cd certs
echo '[1/3] Generating CA Key and Self-Signed Certificate...'
openssl req -new -x509 -days 3650 -extensions v3_ca -keyout ca.key -out ca.crt -subj '/CN=Edge-Servo-Monitoring-CA'
echo '[2/3] Generating Broker Private Key and Certificate...'
openssl req -new -nodes -keyout broker.key -out broker.csr -subj '/CN=rpi5-broker.local'
openssl x509 -req -days 365 -in broker.csr -CA ca.crt -CAkey ca.key -CAcreateserial -out broker.crt
echo '[3/3] Setting restricted filesystem permissions...'
chmod 600 ca.key broker.key
chmod 644 ca.crt broker.crt
echo 'X.509 Certificate Suite Generated Successfully.'
