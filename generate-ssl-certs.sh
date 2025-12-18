#!/bin/bash
# Generate self-signed SSL certificates for development

CERT_DIR="./nginx/certs"
mkdir -p "$CERT_DIR"

openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
    -keyout "$CERT_DIR/key.pem" \
    -out "$CERT_DIR/cert.pem" \
    -subj "/C=TR/ST=Istanbul/L=Istanbul/O=Development/CN=localhost"

echo "✅ SSL certificates generated in $CERT_DIR"
echo "   cert.pem: Certificate"
echo "   key.pem: Private key"

