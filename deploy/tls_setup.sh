#!/bin/bash
# M37-#6: TLS setup
# Генерирует self-signed cert и обновляет systemd unit

set -e

cd /opt/beget/bit-technolog

# 1. Generate certs (idempotent: skip if exist)
if [ ! -f certs/cert.pem ]; then
    echo "🔐 Generating self-signed cert..."
    mkdir -p certs
    openssl req -x509 -newkey rsa:2048 -nodes \
        -out certs/cert.pem -keyout certs/key.pem \
        -days 365 -subj "/CN=bit-technolog.local"
    chmod 600 certs/key.pem
    echo "✅ Cert created"
else
    echo "✅ Cert already exists, skip"
fi

# 2. Update systemd unit to add --ssl-keyfile/--ssl-certfile
SERVICE_FILE=/etc/systemd/system/bit-technolog.service
if ! grep -q "ssl-keyfile" "$SERVICE_FILE"; then
    echo "📝 Updating systemd unit..."
    sed -i 's|--port 8081|--port 8081 --ssl-keyfile=/opt/beget/bit-technolog/certs/key.pem --ssl-certfile=/opt/beget/bit-technolog/certs/cert.pem|' "$SERVICE_FILE"
    systemctl daemon-reload
    echo "✅ systemd updated"
else
    echo "✅ systemd already has TLS, skip"
fi

# 3. Restart
systemctl restart bit-technolog
sleep 3
systemctl is-active bit-technolog
echo "---"
echo "🔒 TLS should be on https://localhost:8081"
