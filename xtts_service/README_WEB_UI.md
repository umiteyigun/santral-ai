# XTTS Web UI - Referans Ses Yönetimi

Referans ses dosyalarını yönetmek için modern web arayüzü.

## 🚀 Kullanım

### 1. XTTS Servisini Başlat

```bash
cd xtts_service
python konusan_asistan_api.py
```

Servis `http://localhost:8020` adresinde çalışacak.

### 2. Web UI'ye Erişim

Tarayıcıda açın:
```
http://localhost:8020
```

veya alternatif route:
```
http://localhost:8020/ui
```

## 📋 Özellikler

### ✅ Aktif Ses Yönetimi
- Aktif referans sesi görüntüleme
- Cache durumu kontrolü
- Ses bilgileri (isim, açıklama, yol)

### 📋 Ses Listesi
- Tüm mevcut referans sesleri listeleme
- Aktif sesi işaretleme
- Tek tıkla aktif ses değiştirme

### 📤 Yeni Ses Yükleme
- WAV, MP3, FLAC formatlarında ses yükleme
- İsim ve açıklama ekleme
- Otomatik listeleme

### 💾 Cache Yönetimi
- Cache'lenmiş embedding sayısı
- Cache dosya boyutları
- Metadata bilgileri

## 🎨 Arayüz Özellikleri

- **Modern ve Responsive**: Mobil ve masaüstü uyumlu
- **Gradient Tasarım**: Modern görünüm
- **Gerçek Zamanlı Güncelleme**: Anlık durum takibi
- **Kolay Kullanım**: Sezgisel arayüz

## 🔧 API Endpoint'leri

Web UI aşağıdaki API endpoint'lerini kullanır:

- `GET /voices` - Tüm sesleri listele
- `GET /voices/active` - Aktif sesi getir
- `POST /voices/set-active` - Aktif sesi değiştir
- `POST /voices/upload` - Yeni ses yükle
- `GET /cache/info` - Cache bilgisi

## 📝 Kullanım Senaryoları

### Senaryo 1: Aktif Sesi Değiştirme

1. Web UI'yi açın: `http://localhost:8020`
2. "Mevcut Sesler" bölümünde istediğiniz sesi bulun
3. "✅ Aktif Yap" butonuna tıklayın
4. Onaylayın
5. Yeni ses aktif olacak ve cache otomatik oluşturulacak

### Senaryo 2: Yeni Ses Yükleme

1. "Yeni Ses Yükle" bölümüne gidin
2. Ses dosyasını seçin (WAV, MP3, FLAC)
3. İsteğe bağlı: İsim ve açıklama ekleyin
4. "📤 Yükle" butonuna tıklayın
5. Yüklenen ses otomatik olarak listeye eklenecek

### Senaryo 3: Cache Durumunu Kontrol Etme

1. "Cache Durumu" bölümüne bakın
2. Cache'lenmiş embedding sayısını görün
3. Cache dosya boyutlarını kontrol edin
4. "🔄 Yenile" butonu ile güncel bilgileri alın

## 🛠️ Teknik Detaylar

### Dosya Yapısı

```
xtts_service/
├── web_ui/
│   ├── templates/
│   │   └── index.html          # Ana HTML sayfası
│   └── static/
│       ├── style.css           # CSS stilleri
│       └── script.js           # JavaScript kodu
├── konusan_asistan_api.py      # FastAPI servisi (Web UI dahil)
└── ...
```

### Port Yapılandırması

- **XTTS API**: Port `8020` (varsayılan)
- Web UI aynı port'ta çalışır (`http://localhost:8020`)

### CORS Ayarları

Web UI farklı bir port'tan erişilebilmesi için CORS ayarları yapılmıştır. Production ortamında daha güvenli ayarlar yapılmalıdır.

## 🐛 Sorun Giderme

### Web UI Görünmüyor

1. XTTS servisinin çalıştığından emin olun
2. `web_ui/` dizininin var olduğunu kontrol edin
3. Tarayıcı konsolunda hata var mı kontrol edin

### API Bağlantı Hatası

1. XTTS API'nin çalıştığını kontrol edin: `curl http://localhost:8020/voices`
2. CORS ayarlarını kontrol edin
3. Network sekmesinde istekleri inceleyin

### Ses Yükleme Hatası

1. Dosya formatının desteklendiğinden emin olun (WAV, MP3, FLAC)
2. Dosya boyutunun uygun olduğundan emin olun
3. XTTS servis loglarını kontrol edin

## 📚 İlgili Dokümantasyon

- [Voice Management README](README_VOICE_MANAGEMENT.md) - CLI komutları
- [Cache Explanation](CACHE_EXPLANATION.md) - Cache mekanizması açıklaması

## 🎯 Gelecek Özellikler

- [ ] Ses önizleme (playback)
- [ ] Ses silme özelliği
- [ ] Toplu ses yükleme
- [ ] Cache temizleme arayüzü
- [ ] Ses karşılaştırma
- [ ] Embedding görselleştirme

