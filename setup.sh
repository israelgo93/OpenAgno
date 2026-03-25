#!/usr/bin/env bash
# ===================================
# OpenAgno - Setup rapido
# ===================================
# Uso: bash setup.sh
#
# Ejecuta todo el onboarding en un solo comando:
# 1. Crea entorno virtual Python
# 2. Instala dependencias
# 3. Lanza el wizard interactivo de configuracion
# 4. Valida el workspace generado
# ===================================

set -e

echo ""
echo "========================================"
echo "  OpenAgno - Setup Automatico"
echo "========================================"
echo ""

# Detectar Python
PYTHON=""
for cmd in python3 python; do
    if command -v "$cmd" &>/dev/null; then
        version=$("$cmd" --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
        major=$(echo "$version" | cut -d. -f1)
        minor=$(echo "$version" | cut -d. -f2)
        if [ "$major" -ge 3 ] && [ "$minor" -ge 11 ]; then
            PYTHON="$cmd"
            break
        fi
    fi
done

if [ -z "$PYTHON" ]; then
    echo "Error: Se requiere Python 3.11 o superior."
    echo "Instala con: sudo apt install python3.12 python3.12-venv"
    exit 1
fi

echo "Python detectado: $($PYTHON --version)"

# Crear entorno virtual si no existe
if [ ! -d ".venv" ]; then
    echo ""
    echo "Creando entorno virtual..."
    $PYTHON -m venv .venv
fi

# Activar entorno virtual
source .venv/bin/activate
echo "Entorno virtual activado: $(which python)"

# Instalar dependencias
echo ""
echo "Instalando dependencias..."
pip install -q --upgrade pip
pip install -q -r requirements.txt

# Lanzar wizard de onboarding
echo ""
echo "Lanzando wizard de configuracion..."
echo ""
python -m management.cli

# Validar workspace
echo ""
echo "Validando workspace..."
python -m management.validator

echo ""
echo "========================================"
echo "  Setup completado!"
echo "========================================"
echo ""
echo "  Comandos disponibles:"
echo ""
echo "  Iniciar:     python gateway.py"
echo "  Daemon:      python service_manager.py start"
echo "  Detener:     python service_manager.py stop"
echo "  Reiniciar:   python service_manager.py restart"
echo "  Estado:      python service_manager.py status"
echo "  Validar:     python -m management.validator"
echo "  Admin:       python -m management.admin status"
echo ""
echo "  Web UI:      http://localhost:8000"
echo "  Studio:      os.agno.com > Add OS > Local"
echo ""
echo "========================================"
