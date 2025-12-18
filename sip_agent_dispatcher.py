#!/usr/bin/env python3
"""
SIP çağrıları için otomatik agent dispatch servisi
LiveKit room'lara participant join olduğunda agent'ı dispatch eder
HTTP API kullanarak
"""
import os
import sys
import time
import requests
import json
from datetime import datetime, timedelta

LIVEKIT_URL = os.getenv("LIVEKIT_URL", "http://livekit:7880")
API_KEY = os.getenv("API_KEY", "devkey")
API_SECRET = os.getenv("API_SECRET", "secret")
AGENT_NAME = "voice-assistant"
POLL_INTERVAL = 15  # seconds - 10'dan 15'e çıkardık, daha az kontrol yapsın

# Dispatch cache: Aynı odaya kısa süre içinde tekrar dispatch etmemek için
# Format: {room_name: last_dispatch_time}
dispatch_cache = {}
# Bu süreç çalıştığı sürece, hangi odalara en az bir kere agent dispatch edildiğini tutar.
# Böylece aynı odaya ikinci/üçüncü agent girmesini tamamen engelleyebiliriz.
dispatched_rooms = set()
CACHE_TTL = 120  # seconds - 120 saniye (2 dakika) içinde aynı odaya tekrar dispatch etme (yedek mekanizma)
# Not: list_participants bazen 0 döndürüyor, bu yüzden hem dispatched_rooms hem de cache'e güveniyoruz

def create_jwt_token():
    """LiveKit JWT token oluştur (Server API için)"""
    try:
        import jwt
        now = datetime.utcnow()
        exp = now + timedelta(hours=1)
        
        # LiveKit Server API için JWT token formatı (server-side işlemler için)
        # Server API için video grant'i ve agent grant'i gerekli
        token = jwt.encode({
            "iss": API_KEY,
            "nbf": int(now.timestamp()),
            "exp": int(exp.timestamp()),
            # Server API için özel grant - tüm odalara erişim
            "video": {
                "room": "*",
                "roomAdmin": True,
                "roomCreate": True,
                "roomJoin": True,
                "roomList": True,
                "canPublish": True,
                "canSubscribe": True,
            },
            # Agent Dispatch API için agent grant'i (obje formatında)
            "agent": {},
        }, API_SECRET, algorithm="HS256")
        
        return token
    except ImportError:
        print("❌ pyjwt not installed, installing...")
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "pyjwt", "--quiet"])
        import jwt
        return create_jwt_token()

def dispatch_agent_to_room(room_name: str):
    """Agent'ı belirtilen odaya dispatch et (HTTP API kullanarak)"""
    try:
        print(f"🤖 Dispatching agent '{AGENT_NAME}' to room: {room_name}")
        
        # Alternatif: Web API'sini kullan (daha güvenilir)
        try:
            web_url = "http://web-ui:3000/api/dispatch-agent"
            response = requests.post(web_url, json={"roomName": room_name}, timeout=10)
            if response.status_code == 200:
                print(f"✅ Agent dispatched to room via Web API: {room_name}")
                return True
            else:
                print(f"⚠️  Web API failed ({response.status_code}), trying direct API...")
        except Exception as e:
            print(f"⚠️  Web API error: {e}, trying direct API...")
        
        # Fallback: Direkt LiveKit HTTP API
        token = create_jwt_token()
        url = f"{LIVEKIT_URL}/twirp/livekit.AgentDispatchService/CreateDispatch"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "room": room_name,
            "agent": AGENT_NAME,
        }
        
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 200:
            print(f"✅ Agent dispatched to room: {room_name}")
            return True
        else:
            print(f"❌ Error dispatching agent: {response.status_code} - {response.text}")
            return False
            
    except Exception as e:
        print(f"❌ Error dispatching agent to room {room_name}: {e}")
        import traceback
        traceback.print_exc()
        return False

def list_rooms():
    """Tüm odaları listele (HTTP API kullanarak)"""
    try:
        token = create_jwt_token()
        url = f"{LIVEKIT_URL}/twirp/livekit.RoomService/ListRooms"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        response = requests.post(url, json={}, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("rooms", [])
        else:
            # Hata durumunda boş liste döndür (log spam'i önlemek için)
            return []
            
    except Exception as e:
        # Hata durumunda boş liste döndür (log spam'i önlemek için)
        return []

def list_participants(room_name: str):
    """Odayaki participant'ları listele (HTTP API kullanarak)"""
    try:
        token = create_jwt_token()
        url = f"{LIVEKIT_URL}/twirp/livekit.RoomService/ListParticipants"
        
        headers = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }
        
        payload = {"room": room_name}
        
        response = requests.post(url, json=payload, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return data.get("participants", [])
        else:
            return []
            
    except Exception as e:
        return []

def check_and_dispatch_agents():
    """Tüm odaları kontrol et ve SIP odalarına agent dispatch et"""
    global dispatch_cache, dispatched_rooms
    try:
        rooms = list_rooms()
        current_time = time.time()
        
        # Cache'i temizle (eski kayıtları sil - cache TTL'den 2 kat daha uzun süre)
        # Cache TTL 60s, bu yüzden 120s'den eski kayıtları sil
        keys_to_remove = [k for k, v in dispatch_cache.items() if current_time - v > CACHE_TTL * 2]
        for k in keys_to_remove:
            del dispatch_cache[k]
        if keys_to_remove:
            print(f"🧹 Cleaned {len(keys_to_remove)} old cache entries (older than {CACHE_TTL * 2}s)")
        
        for room in rooms:
            room_name = room.get("name", "")
            
            # Sadece SIP çağrıları için oluşturulan odaları kontrol et
            if not room_name.startswith("sip-call-"):
                continue
            
            # Eğer bu oda için daha önce dispatch yaptıysak, BİR DAHA ASLA dispatch ETME
            if room_name in dispatched_rooms:
                # Bu oda için zaten en az bir agent dispatch edildi, tekrar denemeye gerek yok
                # (agent düşerse bile yeni agent göndermiyoruz; istenen davranış bu)
                continue

            # ÖNCE CACHE KONTROLÜ - kısa süre içinde tekrar dispatch etmemek için
            last_dispatch = dispatch_cache.get(room_name, 0)
            if last_dispatch > 0:
                cache_age = current_time - last_dispatch
                if cache_age < CACHE_TTL:
                    # Son CACHE_TTL saniye içinde dispatch edilmiş, kesinlikle bekle
                    print(f"⏸️  Room {room_name} in cache (age: {int(cache_age)}s < {CACHE_TTL}s), skipping")
                    continue
            
            # Cache süresi dolmuş veya cache'de yok, şimdi participant kontrolü yap
            participants = list_participants(room_name)
            # Agent identity'leri "agent-AJ_xxx" formatında oluyor
            has_agent = any(
                p.get("identity", "").startswith("agent-") or 
                p.get("identity", "").startswith("voice-assistant") or
                p.get("name", "") == "voice-assistant" 
                for p in participants
            )
            
            if has_agent:
                # Odaya en az bir agent join olmuş, bu odayı dispatched_rooms içine al
                dispatched_rooms.add(room_name)
                dispatch_cache[room_name] = current_time
                print(f"✅ Agent already present in room {room_name}, marking as dispatched (no further agents will be created)")
            else:
                # Agent yok ve cache süresi dolmuş, dispatch et ve hem cache'e hem dispatched_rooms'a kaydet
                print(f"🤖 No agent found in room {room_name}, dispatching...")
                if dispatch_agent_to_room(room_name):
                    dispatch_cache[room_name] = current_time
                    dispatched_rooms.add(room_name)
                    print(f"✅ Agent dispatched to {room_name}, cached for {CACHE_TTL}s (cache now has {len(dispatch_cache)} entries, dispatched_rooms={len(dispatched_rooms)})")
                else:
                    print(f"⚠️  Dispatch failed for {room_name}, not caching / not marking as dispatched")
                
    except Exception as e:
        print(f"❌ Error checking rooms: {e}")
        import traceback
        traceback.print_exc()

def main():
    print("🚀 SIP Agent Dispatcher started")
    print(f"📍 LiveKit URL: {LIVEKIT_URL}")
    print(f"🤖 Agent Name: {AGENT_NAME}")
    print(f"⏱️  Poll Interval: {POLL_INTERVAL}s")
    print()
    
    while True:
        try:
            check_and_dispatch_agents()
            time.sleep(POLL_INTERVAL)
        except KeyboardInterrupt:
            print("\n👋 Shutting down...")
            break
        except Exception as e:
            print(f"❌ Error in main loop: {e}")
            time.sleep(POLL_INTERVAL)

if __name__ == "__main__":
    main()
