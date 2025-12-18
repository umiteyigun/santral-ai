# Sesli Sohbet (Voice Chat) - LiveKit + Ollama + XTTS

LiveKit tabanlı, yerel LLM ve TTS kullanan sesli asistan uygulaması.

## 🏗️ Mimari

- **LiveKit Server**: WebRTC ses iletişimi
- **Agent (Python)**: Ses işleme, STT, LLM entegrasyonu, TTS
- **Web UI (Next.js)**: Kullanıcı arayüzü
- **Nginx**: Reverse proxy

**Harici Servisler:**
- **Ollama**: Yerel LLM (Trendyol LLM modeli)
- **XTTS Service**: Metinden sese (Türkçe)

## 📋 Gereksinimler

1. **Docker & Docker Compose**
2. **Ollama** (host'ta çalışıyor olmalı, port 11434)
3. **XTTS Service** (host'ta çalışıyor olmalı, port 8020)
4. **Node.js & npm** (build için)

## 🚀 Kurulum

### 1. SSL Sertifikaları (Production)

Production için SSL sertifikaları oluşturun:

```bash
./generate-ssl-certs.sh
```

**Development için:** `docker-compose.yml` dosyasında nginx config'ini `nginx.conf.dev` olarak değiştirin (HTTP kullanır).

### 2. Ollama Modelini Yükleyin

```bash
ollama pull ytagalar/trendyol-llm-7b-chat-dpo-v1.0-gguf:latest
```

### 3. XTTS Servisini Başlatın

XTTS servisi host'ta çalışıyor olmalı:

```bash
cd xtts_service
python konusan_asistan_api.py
```

Veya ayrı bir terminal'de çalıştırın. Servis `http://localhost:8020/tts` endpoint'ini dinlemelidir.

### 4. Projeyi Build Edin ve Çalıştırın

```bash
# Web uygulamasını build et
cd web
npm install
npm run build
cd ..

# Docker container'ları build et ve çalıştır
docker-compose build --no-cache
docker-compose up
```

## 🌐 Erişim

- **Web UI**: `http://localhost` (HTTP) veya `https://localhost` (HTTPS)
- **LiveKit**: `ws://localhost:7880` (direkt) veya `wss://localhost/livekit` (nginx üzerinden)

## 🔧 Yapılandırma

### Environment Variables

**Agent:**
- `LIVEKIT_URL`: LiveKit server URL
- `LIVEKIT_API_KEY`: API key
- `LIVEKIT_API_SECRET`: API secret
- `OLLAMA_URL`: Ollama API URL
- `OLLAMA_MODEL`: Kullanılacak model
- `XTTS_API_URL`: XTTS API URL

**Web:**
- `NEXT_PUBLIC_LIVEKIT_URL`: LiveKit WebSocket URL (client-side)
- `LIVEKIT_API_KEY`: API key
- `LIVEKIT_API_SECRET`: API secret
- `LIVEKIT_URL`: LiveKit HTTP URL (server-side)

### XTTS Referans Ses

XTTS servisi için referans ses dosyası `xtts_service/reference.wav` konumunda olmalıdır.

Veya `REFERENCE_AUDIO` environment variable ile özel bir yol belirtebilirsiniz.

## 🐛 Sorun Giderme

### Greeting İki Kez Gönderiliyor

✅ **Düzeltildi**: Race condition sorunu çözüldü. Agent artık sadece bir kez greeting gönderir.

### SSL Sertifika Hatası

Development için `nginx.conf.dev` kullanın veya `generate-ssl-certs.sh` scriptini çalıştırın.

### XTTS Referans Ses Bulunamıyor

`xtts_service/reference.wav` dosyasının var olduğundan emin olun.

### Agent Bağlanamıyor

- Ollama'nın çalıştığından emin olun: `curl http://localhost:11434/api/tags`
- XTTS servisinin çalıştığından emin olun: `curl http://localhost:8020/docs`

## 📝 Notlar

- Agent, kullanıcı bağlandığında otomatik olarak "Merhaba. Nasıl yardımcı olabilirim?" mesajını gönderir
- VAD (Voice Activity Detection) kullanarak konuşma tespiti yapılır
- 500ms sessizlik sonrası konuşma işlenir
- STT için FasterWhisper (small model, CPU) kullanılır

