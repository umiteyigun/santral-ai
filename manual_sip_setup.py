#!/usr/bin/env python3
"""
LiveKit SIP trunk ve dispatch rule'larını manuel olarak oluşturmak için script
JWT token ile LiveKit HTTP API'sini kullanır
"""
import requests
import json
import sys
import os
import time
import hmac
import hashlib
import base64

# LiveKit server bilgileri
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "http://localhost:7880")
API_KEY = os.getenv("API_KEY", "devkey")
API_SECRET = os.getenv("API_SECRET", "secret")

def create_jwt_token(api_key, api_secret):
    """LiveKit JWT token oluştur"""
    header = {
        "alg": "HS256",
        "typ": "JWT"
    }
    
    # Token 1 saat geçerli
    now = int(time.time())
    payload = {
        "iss": api_key,
        "exp": now + 3600,
        "nbf": now - 5
    }
    
    # JWT oluştur
    header_b64 = base64.urlsafe_b64encode(json.dumps(header).encode()).decode().rstrip('=')
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip('=')
    
    message = f"{header_b64}.{payload_b64}"
    signature = hmac.new(
        api_secret.encode(),
        message.encode(),
        hashlib.sha256
    ).digest()
    signature_b64 = base64.urlsafe_b64encode(signature).decode().rstrip('=')
    
    token = f"{message}.{signature_b64}"
    return token

def create_trunk():
    """SIP trunk oluştur"""
    url = f"{LIVEKIT_URL}/twirp/livekit.TelephonyService/CreateSIPTrunk"
    token = create_jwt_token(API_KEY, API_SECRET)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    payload = {
        "trunk": {
            "name": "PBX 1001",
            "numbers": ["1001"],
            "allowed_addresses": [
                "192.168.9.139",
                "192.168.9.0/24",
                "192.168.65.0/24"
            ]
        }
    }
    
    print(f"📞 Creating SIP trunk: {payload['trunk']['name']}")
    print(f"   Numbers: {payload['trunk']['numbers']}")
    print(f"   Allowed addresses: {payload['trunk']['allowed_addresses']}")
    print(f"   URL: {url}")
    print(f"   Token: {token[:50]}...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"   Response status: {response.status_code}")
        print(f"   Response body: {response.text[:200]}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Trunk created successfully")
            print(f"   Response: {json.dumps(result, indent=2)}")
            return result
        else:
            print(f"❌ Error creating trunk: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Exception creating trunk: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_dispatch_rule():
    """Dispatch rule oluştur - DİNAMİK ODA ADI İLE"""
    url = f"{LIVEKIT_URL}/twirp/livekit.TelephonyService/CreateSIPDispatchRule"
    token = create_jwt_token(API_KEY, API_SECRET)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json"
    }
    
    # DİNAMİK: Her çağrı için unique oda (callID template variable kullanarak)
    room_template = "sip-call-{{callID}}"
    participant_template = "sip_{{fromUser}}"
    
    payload = {
        "rule": {
            "name": "Per-Call Room (Dynamic)",
            "criteria": "true",
            "priority": 100,
            "room": room_template,  # ← DİNAMİK: {{callID}} ile her çağrı için ayrı oda
            "participant_identity": participant_template
        }
    }
    
    print(f"\n📋 Creating dispatch rule: {payload['rule']['name']}")
    print(f"   Room template: {room_template} ← DİNAMİK ODA ADI")
    print(f"   Participant identity template: {participant_template}")
    print(f"   URL: {url}")
    print(f"   Token: {token[:50]}...")
    
    try:
        response = requests.post(url, json=payload, headers=headers, timeout=10)
        print(f"   Response status: {response.status_code}")
        print(f"   Response body: {response.text[:200]}")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Dispatch rule created successfully")
            print(f"   Response: {json.dumps(result, indent=2)}")
            return result
        else:
            print(f"❌ Error creating dispatch rule: {response.status_code} - {response.text}")
            return None
    except Exception as e:
        print(f"❌ Exception creating dispatch rule: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🚀 Setting up LiveKit SIP trunk and dispatch rules (MANUAL)...")
    print(f"📍 LiveKit URL: {LIVEKIT_URL}")
    print(f"🔑 API Key: {API_KEY}")
    print()
    
    # Trunk oluştur
    trunk_result = create_trunk()
    print()
    
    # Dispatch rule oluştur (DİNAMİK ODA ADI İLE)
    rule_result = create_dispatch_rule()
    print()
    
    if trunk_result and rule_result:
        print("✅ Setup completed successfully!")
        print("\n📝 Summary:")
        print("   - Trunk: PBX 1001 (number: 1001)")
        print("   - Dispatch Rule: Per-Call Room (Dynamic)")
        print("   - Room template: sip-call-{{callID}}")
        print("   - Her çağrı için otomatik olarak yeni bir oda oluşturulacak!")
        sys.exit(0)
    else:
        print("❌ Setup failed!")
        sys.exit(1)

