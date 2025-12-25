# XTTS Embedding Cache Mekanizması Açıklaması

## 🎯 Nasıl Çalışıyor?

### 1. Referans Ses Dosyası → Hash Hesaplama
Her referans ses dosyası için **MD5 hash** hesaplanır:
```
reference.wav → MD5 hash: "a1b2c3d4e5f6..."
```

### 2. Embedding Hesaplama (İlk Sefer)
- XTTS modeli referans ses dosyasını analiz eder
- **Speaker Embedding** (sesin matematiksel temsili) çıkarılır
- Bu embedding bir **tensor/numpy array** formatındadır

### 3. Cache'leme (3 Seviye)

#### Seviye 1: Memory Cache (RAM)
```python
speaker_embedding_cache = {
    "a1b2c3d4...": <tensor>,  # reference.wav için embedding
    "f6e5d4c3...": <tensor>,  # reference2.wav için embedding
}
```
- ✅ En hızlı erişim
- ❌ Servis restart olunca kaybolur

#### Seviye 2: Disk Cache (Pickle Dosyası)
```
.xtts_cache/
├── embedding_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.pkl  # reference.wav için
├── embedding_f6e5d4c3b2a1z9y8x7w6v5u4t3s2r1q0.pkl  # reference2.wav için
└── embedding_metadata.json                          # İmza/Metadata dosyası
```

**Pickle dosyası içeriği:**
- Embedding tensor'ü (numpy array olarak kaydedilmiş)
- Dosya boyutu: ~1-5 MB (ses dosyasına göre değişir)

#### Seviye 3: Metadata/İmza Dosyası (YENİ!)
```json
{
  "/path/to/reference.wav": {
    "hash": "a1b2c3d4e5f6...",
    "cache_file": "embedding_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.pkl",
    "timestamp": 1703123456.789,
    "file_size": 1589198
  },
  "/path/to/reference2.wav": {
    "hash": "f6e5d4c3b2a1...",
    "cache_file": "embedding_f6e5d4c3b2a1z9y8x7w6v5u4t3s2r1q0.pkl",
    "timestamp": 1703123457.123,
    "file_size": 2837214
  }
}
```

**Metadata dosyası ne işe yarar?**
- ✅ Hangi referans ses dosyasının hangi embedding'e ait olduğunu gösterir
- ✅ Cache dosyalarını temizlerken hangi dosyanın cache'ini sildiğinizi bilirsiniz
- ✅ Cache durumunu kontrol edebilirsiniz
- ✅ Dosya değiştiğinde (timestamp/file_size) cache'in güncel olup olmadığını kontrol edebilirsiniz

## 📊 Cache Akışı

```
1. TTS İsteği Gelir
   ↓
2. Referans Ses Dosyası Belirlenir (aktif ses veya parametre)
   ↓
3. Dosya Hash'i Hesaplanır (MD5)
   ↓
4. Memory Cache Kontrolü
   ├─ ✅ VAR → Embedding döndürülür (EN HIZLI)
   └─ ❌ YOK → Disk Cache Kontrolü
       ├─ ✅ VAR → Disk'ten yüklenir, Memory'e eklenir, döndürülür
       └─ ❌ YOK → XTTS ile Embedding Hesaplanır
           ├─ Memory'e kaydedilir
           ├─ Disk'e kaydedilir (.pkl)
           ├─ Metadata'ya eklenir (.json)
           └─ Embedding döndürülür
```

## 🔍 Cache Kontrolü

### API ile Cache Bilgisi
```bash
# Cache durumunu görüntüle
curl http://localhost:8020/cache/info
```

**Yanıt:**
```json
{
  "cache_directory": "/path/to/.xtts_cache",
  "total_cached_embeddings": 3,
  "metadata_entries": 3,
  "cache_files": [
    {
      "filename": "embedding_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.pkl",
      "size": 2097152,
      "modified": 1703123456.789
    }
  ],
  "metadata": {
    "/path/to/reference.wav": {
      "hash": "a1b2c3d4e5f6...",
      "cache_file": "embedding_a1b2c3d4e5f6g7h8i9j0k1l2m3n4o5p6.pkl",
      "timestamp": 1703123456.789,
      "file_size": 1589198
    }
  }
}
```

### Aktif Ses Cache Durumu
```bash
curl http://localhost:8020/voices/active
```

**Yanıt:**
```json
{
  "active_voice": "reference.wav",
  "path": "/path/to/reference.wav",
  "embedding_cached": true,
  "cache_hash": "a1b2c3d4e5f6g7"
}
```

## 💾 Dosya Yapısı

```
proje/
├── .xtts_cache/                          # Cache dizini
│   ├── embedding_a1b2c3d4...pkl         # Embedding cache dosyası (pickle)
│   ├── embedding_f6e5d4c3...pkl         # Başka bir embedding cache
│   └── embedding_metadata.json           # İmza/Metadata dosyası (JSON)
│
└── xtts_service/
    ├── reference_voices/                  # Referans ses dosyaları
    │   ├── reference.wav                 # Orijinal ses dosyası
    │   └── reference2.wav
    └── voice_config.json                  # Aktif ses config
```

## 🔄 Ses Değiştirme ve Cache

### Senaryo: Yeni Ses Seçildiğinde

1. **Ses Değiştirilir:**
   ```bash
   python change_voice.py reference2.wav
   ```

2. **İlk TTS İsteği:**
   - `reference2.wav` için hash hesaplanır
   - Cache'de yok → Embedding hesaplanır
   - Cache'e kaydedilir (memory + disk + metadata)

3. **Sonraki TTS İstekleri:**
   - Hash ile cache'den direkt yüklenir
   - Embedding tekrar hesaplanmaz ⚡

## 🧹 Cache Temizleme

### Manuel Temizleme
```bash
# Tüm cache'i temizle
rm -rf .xtts_cache/*

# Sadece belirli bir sesin cache'ini temizle
# 1. Metadata'dan hash'i bul
# 2. İlgili .pkl dosyasını sil
# 3. Metadata'dan entry'yi sil
```

### Otomatik Temizleme (Gelecek Özellik)
- Eski cache'leri otomatik temizleme
- Kullanılmayan embedding'leri silme
- Disk alanı yönetimi

## 📝 Özet

**Referans ses dosyası:**
- ❌ Cache'lenmez (orijinal dosya korunur)
- ✅ Embedding'i cache'lenir

**Embedding cache:**
- ✅ Memory'de (hızlı erişim)
- ✅ Disk'te (.pkl dosyası)
- ✅ Metadata'da (hangi dosya → hangi cache mapping'i)

**İmza/Metadata dosyası:**
- ✅ Hangi referans ses dosyasının hangi embedding'e ait olduğunu gösterir
- ✅ Cache durumunu kontrol etmek için kullanılır
- ✅ JSON formatında, okunabilir

## 🎯 Sonuç

**Referans ses dosyası değiştiğinde:**
1. Yeni dosya için hash hesaplanır
2. Cache'de yoksa embedding hesaplanır
3. Yeni embedding cache'lenir
4. Metadata güncellenir
5. Artık yeni ses kullanılır, embedding cache'den gelir ⚡

