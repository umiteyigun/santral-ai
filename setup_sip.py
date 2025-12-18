#!/usr/bin/env python3
"""
LiveKit SIP trunk ve dispatch rule'larını oluşturmak için script
"""
import sys
import os

# LiveKit server bilgileri (environment variables'dan al, yoksa default kullan)
LIVEKIT_URL = os.getenv("LIVEKIT_URL", "http://livekit:7880")
API_KEY = os.getenv("API_KEY", "devkey")
API_SECRET = os.getenv("API_SECRET", "secret")

try:
    from livekit.server_sdk import api
except ImportError:
    print("❌ livekit-server-sdk package not found. Installing...")
    import subprocess
    subprocess.check_call([sys.executable, "-m", "pip", "install", "livekit-server-sdk"])
    from livekit.server_sdk import api

def create_trunk():
    """SIP trunk oluştur"""
    print(f"📞 Creating SIP trunk: PBX 1001")
    print(f"   Numbers: ['1001']")
    print(f"   Allowed addresses: ['192.168.9.139', '192.168.9.0/24', '192.168.65.0/24']")
    try:
        telephony = api.TelephonyService(LIVEKIT_URL, API_KEY, API_SECRET)
        
        trunk = api.SIPTrunk(
            name="PBX 1001",
            numbers=["1001"],
            allowed_addresses=[
                "192.168.9.139",
                "192.168.9.0/24",
                "192.168.65.0/24"
            ]
        )
        
        result = telephony.create_sip_trunk(trunk)
        print(f"✅ Trunk created successfully")
        print(f"   Trunk ID: {result.trunk_id if hasattr(result, 'trunk_id') else 'N/A'}")
        return result
    except Exception as e:
        print(f"❌ Exception creating trunk: {e}")
        import traceback
        traceback.print_exc()
        return None

def create_dispatch_rule():
    """Dispatch rule oluştur"""
    room_template = "sip-call-{{callID}}"  # Her çağrı için unique oda (callID ile)
    participant_template = "sip_{{fromUser}}"
    
    print(f"📋 Creating dispatch rule: Per-Call Room")
    print(f"   Room template: {room_template}")
    print(f"   Participant identity template: {participant_template}")
    try:
        telephony = api.TelephonyService(LIVEKIT_URL, API_KEY, API_SECRET)
        
        rule = api.SIPDispatchRule(
            name="Per-Call Room",
            criteria="true",
            priority=100,
            room=room_template,
            participant_identity=participant_template
        )
        
        result = telephony.create_sip_dispatch_rule(rule)
        print(f"✅ Dispatch rule created successfully")
        print(f"   Rule ID: {result.rule_id if hasattr(result, 'rule_id') else 'N/A'}")
        return result
    except Exception as e:
        print(f"❌ Exception creating dispatch rule: {e}")
        import traceback
        traceback.print_exc()
        return None

if __name__ == "__main__":
    print("🚀 Setting up LiveKit SIP trunk and dispatch rules...")
    print(f"📍 LiveKit URL: {LIVEKIT_URL}")
    print()
    
    # Trunk oluştur
    trunk_result = create_trunk()
    print()
    
    # Dispatch rule oluştur
    rule_result = create_dispatch_rule()
    print()
    
    if trunk_result and rule_result:
        print("✅ Setup completed successfully!")
        sys.exit(0)
    else:
        print("❌ Setup failed!")
        sys.exit(1)

