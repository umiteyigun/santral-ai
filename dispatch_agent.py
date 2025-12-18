#!/usr/bin/env python3
"""
Manuel agent dispatch script - Web API kullanarak
"""
import requests
import sys

room_name = sys.argv[1] if len(sys.argv) > 1 else None

if not room_name:
    print("Usage: python3 dispatch_agent.py <room_name>")
    sys.exit(1)

# Web API'sini kullanarak agent dispatch et
url = "http://web-ui:3000/api/start-chat"
# Ama bu yeni oda oluşturuyor, mevcut odaya dispatch etmiyor

# Alternatif: Direkt LiveKit API'sini kullan
# Ama JWT token formatı hatalı

print(f"❌ Web API mevcut odaya dispatch etmiyor, yeni oda oluşturuyor")
print(f"   Room: {room_name}")
print(f"   Agent dispatch için JWT token formatını düzeltmemiz gerekiyor")

