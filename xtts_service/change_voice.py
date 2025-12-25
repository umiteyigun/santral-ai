#!/usr/bin/env python3
"""
XTTS Reference Voice Changer CLI
Kullanım:
    python change_voice.py <voice_filename>          # Aktif referans sesi değiştir
    python change_voice.py list                       # Mevcut sesleri listele
    python change_voice.py active                     # Aktif sesi göster
    python change_voice.py upload <file_path>         # Yeni ses yükle
"""

import sys
import os
import json
import requests
import argparse

# XTTS API URL
XTTS_API_URL = os.getenv("XTTS_API_URL", "http://localhost:8020")

def list_voices():
    """List all available reference voices"""
    try:
        response = requests.get(f"{XTTS_API_URL}/voices", timeout=5)
        response.raise_for_status()
        data = response.json()
        
        print(f"\n🎤 Aktif Ses: {data.get('active_voice', 'N/A')}")
        print(f"\n📋 Mevcut Sesler ({len(data.get('voices', []))}):")
        print("-" * 60)
        
        for voice in data.get("voices", []):
            active_marker = "✅ [AKTİF]" if voice.get("is_active") else ""
            print(f"  • {voice.get('filename', 'N/A')} {active_marker}")
            if voice.get("name") and voice.get("name") != voice.get("filename"):
                print(f"    İsim: {voice.get('name')}")
            if voice.get("description"):
                print(f"    Açıklama: {voice.get('description')}")
            print()
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ API'ye bağlanılamadı: {e}")
        print(f"   XTTS servisinin çalıştığından emin olun: {XTTS_API_URL}")
        return False

def get_active_voice():
    """Get the currently active reference voice"""
    try:
        response = requests.get(f"{XTTS_API_URL}/voices/active", timeout=5)
        response.raise_for_status()
        data = response.json()
        
        print(f"\n🎤 Aktif Referans Ses:")
        print(f"  Dosya: {data.get('active_voice', 'N/A')}")
        print(f"  Yol: {data.get('path', 'N/A')}")
        print(f"  İsim: {data.get('name', 'N/A')}")
        if data.get("description"):
            print(f"  Açıklama: {data.get('description')}")
        print()
        
        return True
    except requests.exceptions.RequestException as e:
        print(f"❌ API'ye bağlanılamadı: {e}")
        print(f"   XTTS servisinin çalıştığından emin olun: {XTTS_API_URL}")
        return False

def set_active_voice(voice_filename: str):
    """Set the active reference voice"""
    try:
        response = requests.post(
            f"{XTTS_API_URL}/voices/set-active",
            json={"voice_filename": voice_filename},
            timeout=10
        )
        response.raise_for_status()
        data = response.json()
        
        print(f"\n✅ Referans ses değiştirildi!")
        print(f"  Eski: {data.get('old_voice', 'N/A')}")
        print(f"  Yeni: {data.get('active_voice', 'N/A')}")
        print(f"\n💡 Yeni ses ile TTS istekleri artık bu sesi kullanacak.")
        print(f"   Embedding cache otomatik olarak yeni ses için oluşturulacak.\n")
        
        return True
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"❌ Hata: {error_data.get('detail', 'Bilinmeyen hata')}")
            except:
                print(f"❌ Hata: {e.response.text}")
        else:
            print(f"❌ API'ye bağlanılamadı: {e}")
            print(f"   XTTS servisinin çalıştığından emin olun: {XTTS_API_URL}")
        return False

def upload_voice(file_path: str, name: str = None, description: str = None):
    """Upload a new reference voice file"""
    if not os.path.exists(file_path):
        print(f"❌ Dosya bulunamadı: {file_path}")
        return False
    
    if not file_path.lower().endswith(('.wav', '.mp3', '.flac')):
        print(f"❌ Desteklenmeyen dosya formatı. Sadece WAV, MP3 ve FLAC desteklenir.")
        return False
    
    try:
        filename = os.path.basename(file_path)
        with open(file_path, "rb") as f:
            files = {"file": (filename, f, "audio/wav")}
            data = {}
            if name:
                data["name"] = name
            if description:
                data["description"] = description
            
            response = requests.post(
                f"{XTTS_API_URL}/voices/upload",
                files=files,
                data=data,
                timeout=30
            )
            response.raise_for_status()
            result = response.json()
            
            print(f"\n✅ Ses dosyası yüklendi!")
            print(f"  Dosya: {result.get('filename', 'N/A')}")
            print(f"  Yol: {result.get('path', 'N/A')}")
            print(f"\n💡 Bu sesi aktif yapmak için:")
            print(f"   python change_voice.py {result.get('filename', '')}\n")
            
            return True
    except requests.exceptions.RequestException as e:
        if hasattr(e, 'response') and e.response is not None:
            try:
                error_data = e.response.json()
                print(f"❌ Hata: {error_data.get('detail', 'Bilinmeyen hata')}")
            except:
                print(f"❌ Hata: {e.response.text}")
        else:
            print(f"❌ API'ye bağlanılamadı: {e}")
            print(f"   XTTS servisinin çalıştığından emin olun: {XTTS_API_URL}")
        return False

def main():
    parser = argparse.ArgumentParser(
        description="XTTS Referans Ses Yönetimi",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Örnekler:
  %(prog)s list                    # Tüm sesleri listele
  %(prog)s active                  # Aktif sesi göster
  %(prog)s reference2.wav         # Aktif sesi değiştir
  %(prog)s upload /path/to/voice.wav  # Yeni ses yükle
        """
    )
    
    parser.add_argument(
        "command",
        nargs="?",
        help="Komut: list, active, <voice_filename>, veya upload"
    )
    parser.add_argument(
        "file_path",
        nargs="?",
        help="Upload için dosya yolu"
    )
    parser.add_argument(
        "--name",
        help="Upload edilen ses için isim"
    )
    parser.add_argument(
        "--description",
        help="Upload edilen ses için açıklama"
    )
    parser.add_argument(
        "--api-url",
        default=XTTS_API_URL,
        help=f"XTTS API URL (varsayılan: {XTTS_API_URL})"
    )
    
    args = parser.parse_args()
    
    # Override API URL if provided
    global XTTS_API_URL
    if args.api_url:
        XTTS_API_URL = args.api_url
    
    if not args.command:
        parser.print_help()
        return 1
    
    if args.command == "list":
        success = list_voices()
        return 0 if success else 1
    elif args.command == "active":
        success = get_active_voice()
        return 0 if success else 1
    elif args.command == "upload":
        if not args.file_path:
            print("❌ Upload için dosya yolu gerekli: python change_voice.py upload <file_path>")
            return 1
        success = upload_voice(args.file_path, args.name, args.description)
        return 0 if success else 1
    else:
        # Assume it's a voice filename to set as active
        success = set_active_voice(args.command)
        return 0 if success else 1

if __name__ == "__main__":
    sys.exit(main())

