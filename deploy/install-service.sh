#!/usr/bin/env bash
# ===================================
# OpenAgno — Instalar servicio systemd
# ===================================
# Uso: sudo bash deploy/install-service.sh
#
# Genera un unit file adaptado a la ruta actual
# y lo instala en systemd.
# ===================================

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
CURRENT_USER="${SUDO_USER:-$USER}"
SERVICE_NAME="openagno"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

echo ""
echo "  OpenAgno — Instalador de servicio systemd"
echo "  Proyecto: $PROJECT_DIR"
echo "  Usuario:  $CURRENT_USER"
echo ""

if [ "$EUID" -ne 0 ]; then
    echo "  Error: Ejecuta con sudo"
    echo "  sudo bash deploy/install-service.sh"
    exit 1
fi

if [ ! -f "$PROJECT_DIR/.venv/bin/python" ]; then
    echo "  Error: No se encontro .venv/bin/python"
    echo "  Ejecuta primero: bash setup.sh"
    exit 1
fi

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=OpenAgno AI Agent Platform
After=network.target
Documentation=https://github.com/israelgo93/OpenAgno

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${PROJECT_DIR}
Environment=OPENAGNO_ROOT=${PROJECT_DIR}
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${PROJECT_DIR}/.venv/bin/python gateway.py
Restart=on-failure
RestartSec=5
StandardOutput=append:${PROJECT_DIR}/gateway.log
StandardError=append:${PROJECT_DIR}/gateway.log

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"

echo "  [OK] Servicio gateway instalado: $SERVICE_FILE"

# === WhatsApp QR Bridge (opcional) ===
BRIDGE_DIR="$PROJECT_DIR/bridges/whatsapp-qr"
BRIDGE_SERVICE_NAME="openagno-whatsapp-bridge"
BRIDGE_SERVICE_FILE="/etc/systemd/system/${BRIDGE_SERVICE_NAME}.service"

if [ -f "$BRIDGE_DIR/index.js" ] && command -v node &>/dev/null; then
    NODE_BIN="$(command -v node)"

    cat > "$BRIDGE_SERVICE_FILE" <<BEOF
[Unit]
Description=OpenAgno WhatsApp QR Bridge (Baileys)
After=network.target ${SERVICE_NAME}.service
Documentation=https://github.com/israelgo93/OpenAgno
PartOf=${SERVICE_NAME}.service

[Service]
Type=simple
User=${CURRENT_USER}
WorkingDirectory=${BRIDGE_DIR}
Environment=GATEWAY_URL=http://localhost:8000
Environment=SESSION_DIR=${BRIDGE_DIR}/session
Environment=BRIDGE_PORT=3001
EnvironmentFile=${PROJECT_DIR}/.env
ExecStart=${NODE_BIN} index.js
Restart=on-failure
RestartSec=5
StandardOutput=append:${BRIDGE_DIR}/bridge.log
StandardError=append:${BRIDGE_DIR}/bridge.log

[Install]
WantedBy=multi-user.target
BEOF

    systemctl daemon-reload
    systemctl enable "$BRIDGE_SERVICE_NAME"
    echo "  [OK] Servicio bridge instalado: $BRIDGE_SERVICE_FILE"
else
    echo "  [--] Bridge WhatsApp QR omitido (Node.js no encontrado o bridge no existe)"
fi

echo ""
echo "  Comandos:"
echo "    sudo systemctl start openagno                    # Iniciar gateway"
echo "    sudo systemctl stop openagno                     # Detener gateway"
echo "    sudo systemctl restart openagno                  # Reiniciar gateway"
echo "    sudo systemctl status openagno                   # Estado gateway"
echo "    journalctl -u openagno -f                        # Logs gateway"
echo ""
echo "    sudo systemctl start openagno-whatsapp-bridge    # Iniciar bridge QR"
echo "    sudo systemctl stop openagno-whatsapp-bridge     # Detener bridge QR"
echo "    sudo systemctl status openagno-whatsapp-bridge   # Estado bridge QR"
echo "    journalctl -u openagno-whatsapp-bridge -f        # Logs bridge QR"
echo ""
