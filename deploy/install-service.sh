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

echo "  [OK] Servicio instalado: $SERVICE_FILE"
echo ""
echo "  Comandos:"
echo "    sudo systemctl start openagno     # Iniciar"
echo "    sudo systemctl stop openagno      # Detener"
echo "    sudo systemctl restart openagno   # Reiniciar"
echo "    sudo systemctl status openagno    # Estado"
echo "    journalctl -u openagno -f         # Logs en vivo"
echo ""
