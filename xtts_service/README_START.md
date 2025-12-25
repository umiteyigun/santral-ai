# XTTS Service Start/Stop Scripts

XTTS servisini başlatmak ve durdurmak için kullanılan script'ler.

## 🚀 Başlatma

### Yöntem 1: Start Script (Önerilen)

```bash
cd xtts_service
./start_xtts.sh
```

Script otomatik olarak:
1. ✅ Çalışan XTTS servisini durdurur
2. ✅ Virtualenv'i bulur ve aktif eder
3. ✅ Gerekli paketleri kontrol eder
4. ✅ XTTS servisini başlatır (Web UI dahil)

### Yöntem 2: Manuel Başlatma

```bash
cd xtts_service

# Virtualenv'i aktif et (eğer varsa)
source venv/bin/activate  # veya env/bin/activate

# Servisi başlat
python3 konusan_asistan_api.py
```

## 🛑 Durdurma

### Yöntem 1: Stop Script

```bash
cd xtts_service
./stop_xtts.sh
```

### Yöntem 2: Manuel Durdurma

```bash
# Process ID'yi bul
ps aux | grep konusan_asistan_api

# Durdur
kill <PID>

# Veya force kill
kill -9 <PID>
```

### Yöntem 3: Ctrl+C

Eğer servis foreground'da çalışıyorsa, `Ctrl+C` ile durdurabilirsiniz.

## 📋 Virtualenv Yapılandırması

Script otomatik olarak virtualenv'i şu sırayla arar:

1. `xtts_service/venv/`
2. `xtts_service/env/`
3. `xtts_service/.venv/`
4. `../venv/` (üst dizin)
5. `../env/` (üst dizin)
6. `$XTTS_VENV_PATH` (environment variable)

### Environment Variable ile Virtualenv Belirtme

```bash
export XTTS_VENV_PATH=/path/to/your/venv
./start_xtts.sh
```

## 🌐 Erişim

Servis başladıktan sonra:

- **Web UI**: http://localhost:8020
- **API Docs**: http://localhost:8020/docs
- **API Endpoints**: http://localhost:8020/voices, etc.

## 🔧 Sorun Giderme

### Port Zaten Kullanılıyor

```bash
# Port'u kullanan process'i bul
lsof -i :8020

# Durdur
kill <PID>
```

### Virtualenv Bulunamadı

1. Virtualenv'in doğru dizinde olduğundan emin olun
2. Veya `XTTS_VENV_PATH` environment variable'ını ayarlayın
3. Veya script'i virtualenv olmadan çalıştırın (sistem Python kullanılır)

### Paket Eksik

```bash
# Virtualenv'i aktif et
source venv/bin/activate

# Gerekli paketleri yükle
pip install fastapi uvicorn[standard] jinja2 python-multipart torch TTS soundfile
```

## 📝 Notlar

- Script, çalışan servisi otomatik olarak durdurur
- Web UI, XTTS API ile aynı serviste çalışır (ayrı port gerekmez)
- Servis foreground'da çalışır (loglar görünür)
- Arka planda çalıştırmak için `nohup` veya `screen` kullanabilirsiniz

## 🔄 Arka Planda Çalıştırma

```bash
# nohup ile
nohup ./start_xtts.sh > xtts.log 2>&1 &

# screen ile
screen -S xtts
./start_xtts.sh
# Ctrl+A, D ile detach
```

## 📊 Log Kontrolü

```bash
# nohup log'u
tail -f xtts.log

# screen session'ına geri dön
screen -r xtts
```

