# XTTS Referans Ses Yönetimi

Bu sistem, XTTS servisi için referans ses dosyalarını yönetmenizi sağlar. Referans sesler bir kez analiz edilir ve cache'lenir, böylece her TTS isteğinde tekrar analiz edilmez.

## 📁 Dizin Yapısı

```
xtts_service/
├── reference_voices/      # Referans ses dosyaları burada tutulur
│   ├── voice1.wav
│   ├── voice2.wav
│   └── ...
├── voice_config.json      # Aktif ses ve ses listesi config dosyası
└── change_voice.py        # CLI komutu
```

## 🎤 CLI Komutları

### Sesleri Listele
```bash
python xtts_service/change_voice.py list
```

### Aktif Sesi Göster
```bash
python xtts_service/change_voice.py active
```

### Aktif Sesi Değiştir
```bash
python xtts_service/change_voice.py reference2.wav
```

### Yeni Ses Yükle
```bash
python xtts_service/change_voice.py upload /path/to/voice.wav
```

İsim ve açıklama ile:
```bash
python xtts_service/change_voice.py upload /path/to/voice.wav --name "Kadın Ses" --description "Profesyonel kadın sesi"
```

## 🌐 API Endpoint'leri

### Tüm Sesleri Listele
```bash
curl http://localhost:8020/voices
```

### Aktif Sesi Göster
```bash
curl http://localhost:8020/voices/active
```

### Aktif Sesi Değiştir
```bash
curl -X POST http://localhost:8020/voices/set-active \
  -H "Content-Type: application/json" \
  -d '{"voice_filename": "reference2.wav"}'
```

### Yeni Ses Yükle
```bash
curl -X POST http://localhost:8020/voices/upload \
  -F "file=@/path/to/voice.wav" \
  -F "name=Yeni Ses" \
  -F "description=Ses açıklaması"
```

## ⚙️ Config Dosyası

`voice_config.json` dosyası şu formatta:

```json
{
  "active_voice": "reference.wav",
  "voices": {
    "reference.wav": {
      "name": "Default Voice",
      "path": "reference.wav",
      "description": "Default reference voice"
    },
    "reference2.wav": {
      "name": "Kadın Ses",
      "path": "reference2.wav",
      "description": "Profesyonel kadın sesi"
    }
  }
}
```

## 🔄 Cache Mekanizması

- Her referans ses dosyası için embedding bir kez hesaplanır
- Embedding'ler hem memory'de hem disk'te (`.xtts_cache/`) cache'lenir
- Ses değiştirildiğinde, yeni ses için embedding otomatik olarak hesaplanır ve cache'lenir
- Eski seslerin cache'leri korunur (gelecekte tekrar kullanılabilir)

## 💡 Kullanım Senaryoları

### Senaryo 1: Farklı Seslerle Test
```bash
# Sesleri listele
python xtts_service/change_voice.py list

# Farklı bir ses seç
python xtts_service/change_voice.py reference2.wav

# Test et - yeni ses kullanılacak
```

### Senaryo 2: Yeni Ses Ekle ve Kullan
```bash
# Yeni ses yükle
python xtts_service/change_voice.py upload /path/to/new_voice.wav --name "Özel Ses"

# Aktif yap
python xtts_service/change_voice.py new_voice.wav
```

### Senaryo 3: API ile Otomatik Değiştirme
```bash
# Script içinde kullanım
curl -X POST http://localhost:8020/voices/set-active \
  -H "Content-Type: application/json" \
  -d '{"voice_filename": "reference2.wav"}'
```

## 🚀 Arka Plan Kullanımı

CLI komutunu arka planda veya script içinde kullanabilirsiniz:

```bash
# Arka planda çalıştır
nohup python xtts_service/change_voice.py reference2.wav > /dev/null 2>&1 &

# Cron job ile periyodik değiştirme
# 0 9 * * * cd /path/to/project && python xtts_service/change_voice.py morning_voice.wav
```

## 📝 Notlar

- Ses değişikliği anında etkili olur (servis restart gerekmez)
- Embedding cache'i otomatik olarak yönetilir
- Eski seslerin cache'leri korunur (disk alanı tasarrufu için manuel temizlenebilir)
- Desteklenen formatlar: WAV, MP3, FLAC

