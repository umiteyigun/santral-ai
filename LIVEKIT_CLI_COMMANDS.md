# LiveKit CLI (lk) Komutları

## 🔐 Temel Ayarlar

```bash
# Developer credentials kullan (local için)
--dev

# Veya manuel credentials
--url http://localhost:7880
--api-key devkey
--api-secret secret
```

---

## 📋 ODA İŞLEMLERİ

### Tüm Odaları Listele
```bash
lk room list --dev
lk room list --dev --json  # JSON formatında
lk room list --dev sip-call-*  # Belirli pattern ile filtrele
```

### Belirli Bir Odayı Detaylı Göster
```bash
lk room list --dev ROOM_NAME
lk room list --dev --json ROOM_NAME
```

### Oda Oluştur
```bash
lk room create --dev ROOM_NAME
```

### Oda Sil
```bash
lk room delete --dev ROOM_NAME
```

---

## 👥 PARTICIPANT İŞLEMLERİ

### Odadaki Tüm Participant'ları Listele
```bash
lk room participants list --dev ROOM_NAME
lk room participants list --dev ROOM_NAME --json  # JSON formatında
```

### Belirli Bir Participant'ı Getir
```bash
lk room participants get --dev ROOM_NAME PARTICIPANT_IDENTITY
```

### Participant'ı Odadan Çıkar
```bash
lk room participants remove --dev ROOM_NAME PARTICIPANT_IDENTITY
```

### Participant'ı Başka Odaya Taşı
```bash
lk room participants move --dev ROOM_NAME PARTICIPANT_IDENTITY TARGET_ROOM_NAME
```

### Participant'ı Başka Odaya Forward Et
```bash
lk room participants forward --dev ROOM_NAME PARTICIPANT_IDENTITY TARGET_ROOM_NAME
```

### Participant Metadata Güncelle
```bash
lk room participants update --dev ROOM_NAME PARTICIPANT_IDENTITY --metadata '{"key":"value"}'
```

---

## 📞 SIP İŞLEMLERİ

### SIP Dispatch Rules Listele
```bash
lk sip dispatch list --dev
lk sip dispatch list --dev --json
```

### SIP Dispatch Rule Getir
```bash
lk sip dispatch get --dev RULE_NAME
```

### SIP Dispatch Rule Oluştur
```bash
lk sip dispatch create --dev \
  --name "Rule Name" \
  --criteria "true" \
  --priority 100 \
  --room "sip-call-{{callID}}" \
  --participant-identity "sip_{{fromUser}}"
```

### SIP Dispatch Rule Sil
```bash
lk sip dispatch delete --dev RULE_NAME
```

### Inbound SIP Trunk Listele
```bash
lk sip inbound list --dev
```

### Outbound SIP Trunk Listele
```bash
lk sip outbound list --dev
```

### SIP Participant'ları Listele
```bash
lk sip participant list --dev
```

---

## 🤖 AGENT DISPATCH İŞLEMLERİ

### Tüm Agent Dispatch'leri Listele
```bash
lk dispatch list --dev ROOM_NAME
lk dispatch list --dev ROOM_NAME --json
```

### Belirli Bir Dispatch Getir
```bash
lk dispatch get --dev ROOM_NAME DISPATCH_ID
```

### Agent Dispatch Oluştur
```bash
lk dispatch create --dev ROOM_NAME AGENT_NAME
lk dispatch create --dev ROOM_NAME voice-assistant
```

### Agent Dispatch Sil
```bash
lk dispatch delete --dev ROOM_NAME DISPATCH_ID
```

---

## 🎯 PRATİK ÖRNEKLER

### Aktif Tüm Odaları ve Participant Sayılarını Göster
```bash
lk room list --dev
```

### Belirli Bir Odada Kimler Var?
```bash
lk room participants list --dev sip-call-ABC123
```

### SIP Odalarını Filtrele
```bash
lk room list --dev sip-call-*
```

### Odadaki Agent'ları Bul
```bash
lk room participants list --dev ROOM_NAME | grep agent-
```

### Tüm SIP Dispatch Rules'ları Göster
```bash
lk sip dispatch list --dev
```

### Bir Odadaki Tüm Dispatch'leri Göster
```bash
lk dispatch list --dev ROOM_NAME
```

---

## 📊 JSON Çıktı Örnekleri

### Oda Listesi (JSON)
```bash
lk room list --dev --json | jq '.'
```

### Participant Listesi (JSON)
```bash
lk room participants list --dev ROOM_NAME --json | jq '.'
```

### SIP Dispatch Rules (JSON)
```bash
lk sip dispatch list --dev --json | jq '.'
```

---

## 🔧 Environment Variables

```bash
export LIVEKIT_URL=http://localhost:7880
export LIVEKIT_API_KEY=devkey
export LIVEKIT_API_SECRET=secret

# Sonra --dev yerine direkt komutları kullanabilirsin
lk room list
lk room participants list ROOM_NAME
```

---

## 💡 İPUÇLARI

1. **--dev flag'i**: Local LiveKit server için otomatik olarak `devkey` ve `secret` kullanır
2. **--json flag'i**: Çıktıyı JSON formatında verir, `jq` ile parse edebilirsin
3. **--verbose flag'i**: Detaylı log çıktısı için
4. **--curl flag'i**: API çağrılarını curl komutları olarak gösterir (debug için)

---

## 📝 Örnek Kullanım Senaryoları

### Senaryo 1: Aktif bir SIP çağrısını kontrol et
```bash
# Tüm SIP odalarını listele
lk room list --dev sip-call-*

# Belirli bir odada kimler var?
lk room participants list --dev sip-call-ABC123

# Bu odada agent var mı?
lk room participants list --dev sip-call-ABC123 | grep agent-
```

### Senaryo 2: Dispatch rule'ları kontrol et
```bash
# Tüm dispatch rules'ları göster
lk sip dispatch list --dev

# Belirli bir rule'u detaylı göster
lk sip dispatch get --dev "Per-Call Room"
```

### Senaryo 3: Agent dispatch'leri yönet
```bash
# Bir odadaki tüm dispatch'leri listele
lk dispatch list --dev sip-call-ABC123

# Yeni bir agent dispatch oluştur
lk dispatch create --dev sip-call-ABC123 voice-assistant
```

