#!/bin/bash

# XTTS Service Start Script
# Virtualenv ile XTTS servisini başlatır (Web UI dahil)

set -e

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Script dizini
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Port
PORT=8020

echo -e "${BLUE}🚀 XTTS Service Başlatılıyor...${NC}"

# 1. Çalışan XTTS servisini durdur
echo -e "${YELLOW}📋 Çalışan XTTS servisleri kontrol ediliyor...${NC}"
XTTS_PID=$(ps aux | grep -E "konusan_asistan_api|uvicorn.*8020" | grep -v grep | awk '{print $2}' | head -1)

if [ ! -z "$XTTS_PID" ]; then
    echo -e "${YELLOW}⚠️  Çalışan XTTS servisi bulundu (PID: $XTTS_PID), durduruluyor...${NC}"
    kill "$XTTS_PID" 2>/dev/null || true
    sleep 2
    
    # Hala çalışıyorsa force kill
    if ps -p "$XTTS_PID" > /dev/null 2>&1; then
        echo -e "${YELLOW}⚠️  Servis hala çalışıyor, force kill yapılıyor...${NC}"
        kill -9 "$XTTS_PID" 2>/dev/null || true
        sleep 1
    fi
    echo -e "${GREEN}✅ Eski servis durduruldu${NC}"
else
    echo -e "${GREEN}✅ Çalışan servis yok${NC}"
fi

# 2. Port kontrolü
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${RED}❌ Port $PORT zaten kullanılıyor!${NC}"
    echo -e "${YELLOW}Port'u kullanan process:${NC}"
    lsof -Pi :$PORT -sTCP:LISTEN
    exit 1
fi

# 3. Virtualenv bulma
VENV_PATH=""

# Seçenek 1: Environment variable (en yüksek öncelik)
if [ ! -z "$XTTS_VENV_PATH" ] && [ -f "$XTTS_VENV_PATH/bin/activate" ]; then
    VENV_PATH="$XTTS_VENV_PATH"
# Seçenek 2: Kullanıcının belirttiği varsayılan path
elif [ -f "/Users/umiteyigun/xtts-venv/bin/activate" ]; then
    VENV_PATH="/Users/umiteyigun/xtts-venv"
# Seçenek 3: Script dizininde venv
elif [ -d "$SCRIPT_DIR/venv" ] && [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
    VENV_PATH="$SCRIPT_DIR/venv"
elif [ -d "$SCRIPT_DIR/env" ] && [ -f "$SCRIPT_DIR/env/bin/activate" ]; then
    VENV_PATH="$SCRIPT_DIR/env"
elif [ -d "$SCRIPT_DIR/.venv" ] && [ -f "$SCRIPT_DIR/.venv/bin/activate" ]; then
    VENV_PATH="$SCRIPT_DIR/.venv"
# Seçenek 4: Üst dizinde venv
elif [ -d "$(dirname "$SCRIPT_DIR")/venv" ] && [ -f "$(dirname "$SCRIPT_DIR")/venv/bin/activate" ]; then
    VENV_PATH="$(dirname "$SCRIPT_DIR")/venv"
elif [ -d "$(dirname "$SCRIPT_DIR")/env" ] && [ -f "$(dirname "$SCRIPT_DIR")/env/bin/activate" ]; then
    VENV_PATH="$(dirname "$SCRIPT_DIR")/env"
fi

# Virtualenv kontrolü
if [ -z "$VENV_PATH" ] || [ ! -f "$VENV_PATH/bin/activate" ]; then
    echo -e "${YELLOW}⚠️  Virtualenv bulunamadı!${NC}"
    echo -e "${YELLOW}Lütfen virtualenv path'ini girin (veya ENTER'a basın - sistem Python kullanılacak):${NC}"
    echo -e "${BLUE}Örnek: /Users/umiteyigun/projeler/sohbet_local/venv${NC}"
    read -p "Virtualenv path: " USER_VENV_PATH
    
    if [ ! -z "$USER_VENV_PATH" ] && [ -f "$USER_VENV_PATH/bin/activate" ]; then
        VENV_PATH="$USER_VENV_PATH"
        USE_VENV=true
        echo -e "${GREEN}✅ Virtualenv kullanılacak: $VENV_PATH${NC}"
    elif [ ! -z "$USER_VENV_PATH" ]; then
        echo -e "${RED}❌ Geçersiz virtualenv path: $USER_VENV_PATH${NC}"
        echo -e "${YELLOW}Sistem Python kullanılacak (torch gibi paketler yüklü olmayabilir)${NC}"
        USE_VENV=false
    else
        echo -e "${YELLOW}⚠️  Sistem Python kullanılacak (torch gibi paketler yüklü olmayabilir)${NC}"
        USE_VENV=false
    fi
else
    echo -e "${GREEN}✅ Virtualenv bulundu: $VENV_PATH${NC}"
    USE_VENV=true
fi

# 4. Virtualenv'i aktif et ve servisi başlat
if [ "$USE_VENV" = true ]; then
    echo -e "${BLUE}📦 Virtualenv aktif ediliyor...${NC}"
    source "$VENV_PATH/bin/activate"
    echo -e "${GREEN}✅ Virtualenv aktif${NC}"
fi

# 5. Gerekli paketleri kontrol et
echo -e "${BLUE}📋 Gerekli paketler kontrol ediliyor...${NC}"
MISSING_PACKAGES=""

if ! python3 -c "import fastapi" 2>/dev/null; then
    MISSING_PACKAGES="$MISSING_PACKAGES fastapi"
fi
if ! python3 -c "import uvicorn" 2>/dev/null; then
    MISSING_PACKAGES="$MISSING_PACKAGES uvicorn[standard]"
fi
if ! python3 -c "import jinja2" 2>/dev/null; then
    MISSING_PACKAGES="$MISSING_PACKAGES jinja2"
fi
if ! python3 -c "import multipart" 2>/dev/null; then
    MISSING_PACKAGES="$MISSING_PACKAGES python-multipart"
fi

if [ ! -z "$MISSING_PACKAGES" ]; then
    echo -e "${YELLOW}⚠️  Eksik paketler bulundu, yükleniyor: $MISSING_PACKAGES${NC}"
    pip install $MISSING_PACKAGES > /dev/null 2>&1 || {
        echo -e "${RED}❌ Paket yükleme hatası! Manuel olarak yükleyin:${NC}"
        echo "   pip install $MISSING_PACKAGES"
    }
else
    echo -e "${GREEN}✅ Tüm gerekli paketler yüklü${NC}"
fi

# 6. Servisi başlat
echo -e "${BLUE}🚀 XTTS servisi başlatılıyor...${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${GREEN}✅ XTTS Service: http://localhost:$PORT${NC}"
echo -e "${GREEN}✅ Web UI: http://localhost:$PORT${NC}"
echo -e "${GREEN}✅ API Docs: http://localhost:$PORT/docs${NC}"
echo -e "${GREEN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""
echo -e "${YELLOW}💡 Servisi durdurmak için Ctrl+C basın${NC}"
echo ""

# Servisi başlat (foreground)
python3 konusan_asistan_api.py

