#!/bin/bash

# XTTS Service Stop Script
# Çalışan XTTS servisini durdurur

set -e

# Renkler
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Port
PORT=8020

echo -e "${BLUE}🛑 XTTS Service Durduruluyor...${NC}"

# Çalışan XTTS servislerini bul
XTTS_PIDS=$(ps aux | grep -E "konusan_asistan_api|uvicorn.*8020" | grep -v grep | awk '{print $2}')

if [ -z "$XTTS_PIDS" ]; then
    echo -e "${YELLOW}⚠️  Çalışan XTTS servisi bulunamadı${NC}"
    exit 0
fi

echo -e "${YELLOW}📋 Çalışan servisler:${NC}"
ps aux | grep -E "konusan_asistan_api|uvicorn.*8020" | grep -v grep

# Servisleri durdur
for PID in $XTTS_PIDS; do
    echo -e "${YELLOW}🛑 Servis durduruluyor (PID: $PID)...${NC}"
    kill "$PID" 2>/dev/null || true
done

sleep 2

# Hala çalışan varsa force kill
REMAINING_PIDS=$(ps aux | grep -E "konusan_asistan_api|uvicorn.*8020" | grep -v grep | awk '{print $2}')
if [ ! -z "$REMAINING_PIDS" ]; then
    echo -e "${YELLOW}⚠️  Bazı servisler hala çalışıyor, force kill yapılıyor...${NC}"
    for PID in $REMAINING_PIDS; do
        kill -9 "$PID" 2>/dev/null || true
    done
    sleep 1
fi

# Port kontrolü
if lsof -Pi :$PORT -sTCP:LISTEN -t >/dev/null 2>&1 ; then
    echo -e "${RED}❌ Port $PORT hala kullanılıyor!${NC}"
    lsof -Pi :$PORT -sTCP:LISTEN
    exit 1
fi

echo -e "${GREEN}✅ XTTS servisi durduruldu${NC}"

