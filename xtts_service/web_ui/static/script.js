// API URL - eğer web UI ayrı bir port'ta çalışıyorsa XTTS API URL'ini kullan
const API_URL = window.location.origin.includes(':8696') 
    ? 'http://localhost:8020'  // Web UI ayrı port'ta ise XTTS API'ye bağlan
    : window.location.origin;   // Aynı port'ta ise aynı origin kullan

// Sayfa yüklendiğinde
document.addEventListener('DOMContentLoaded', () => {
    loadActiveVoice();
    loadVoices();
    loadCacheInfo();
    
    // Upload form handler
    document.getElementById('uploadForm').addEventListener('submit', handleUpload);
});

// Aktif sesi yükle
async function loadActiveVoice() {
    try {
        const response = await fetch(`${API_URL}/voices/active`);
        const data = await response.json();
        
        const activeVoiceInfo = document.getElementById('activeVoiceInfo');
        const cacheBadge = data.embedding_cached 
            ? '<span class="cache-badge cached">✅ Cache\'li</span>' 
            : '<span class="cache-badge not-cached">❌ Cache\'siz</span>';
        
        activeVoiceInfo.innerHTML = `
            <div class="info-row">
                <span class="info-label">Dosya:</span>
                <span class="info-value">${data.active_voice}</span>
            </div>
            <div class="info-row">
                <span class="info-label">İsim:</span>
                <span class="info-value">${data.name || data.active_voice}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Yol:</span>
                <span class="info-value" style="font-size: 0.9em; font-family: monospace;">${data.path}</span>
            </div>
            <div class="info-row">
                <span class="info-label">Cache Durumu:</span>
                <span class="info-value">${cacheBadge}</span>
            </div>
            ${data.description ? `
            <div class="info-row">
                <span class="info-label">Açıklama:</span>
                <span class="info-value">${data.description}</span>
            </div>
            ` : ''}
        `;
    } catch (error) {
        document.getElementById('activeVoiceInfo').innerHTML = 
            `<div style="color: #ef4444;">❌ Hata: ${error.message}</div>`;
    }
}

// Sesleri yükle
async function loadVoices() {
    try {
        const response = await fetch(`${API_URL}/voices`);
        const data = await response.json();
        
        const voicesList = document.getElementById('voicesList');
        
        if (data.voices && data.voices.length === 0) {
            voicesList.innerHTML = '<div class="loading">Henüz ses dosyası yok</div>';
            return;
        }
        
        voicesList.innerHTML = data.voices.map(voice => {
            const isActive = voice.is_active;
            const cacheBadge = voice.is_active && data.active_voice === voice.filename
                ? '<span class="cache-badge cached">✅ Aktif</span>'
                : '';
            
            return `
                <div class="voice-item ${isActive ? 'active' : ''}">
                    <div class="voice-info">
                        <div class="voice-name">
                            ${voice.name || voice.filename}
                            ${cacheBadge}
                        </div>
                        <div class="voice-filename">${voice.filename}</div>
                        ${voice.description ? `<div class="voice-description">${voice.description}</div>` : ''}
                    </div>
                    <div class="voice-actions">
                        ${!isActive ? `
                            <button class="btn btn-success" onclick="setActiveVoice('${voice.filename}')">
                                ✅ Aktif Yap
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
    } catch (error) {
        document.getElementById('voicesList').innerHTML = 
            `<div style="color: #ef4444;">❌ Hata: ${error.message}</div>`;
    }
}

// Aktif sesi değiştir
async function setActiveVoice(filename) {
    if (!confirm(`"${filename}" dosyasını aktif ses olarak ayarlamak istediğinize emin misiniz?`)) {
        return;
    }
    
    try {
        const response = await fetch(`${API_URL}/voices/set-active`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ voice_filename: filename })
        });
        
        const data = await response.json();
        
        if (response.ok) {
            alert(`✅ Başarılı!\n\nEski ses: ${data.old_voice}\nYeni ses: ${data.active_voice}\n\nYeni ses ile TTS istekleri artık bu sesi kullanacak.`);
            loadActiveVoice();
            loadVoices();
            loadCacheInfo();
        } else {
            alert(`❌ Hata: ${data.detail || 'Bilinmeyen hata'}`);
        }
    } catch (error) {
        alert(`❌ Hata: ${error.message}`);
    }
}

// Dosya yükle
async function handleUpload(e) {
    e.preventDefault();
    
    const fileInput = document.getElementById('voiceFile');
    const nameInput = document.getElementById('voiceName');
    const descInput = document.getElementById('voiceDescription');
    const statusDiv = document.getElementById('uploadStatus');
    
    if (!fileInput.files[0]) {
        statusDiv.className = 'status-message error';
        statusDiv.textContent = '❌ Lütfen bir dosya seçin';
        return;
    }
    
    const formData = new FormData();
    formData.append('file', fileInput.files[0]);
    if (nameInput.value) {
        formData.append('name', nameInput.value);
    }
    if (descInput.value) {
        formData.append('description', descInput.value);
    }
    
    statusDiv.className = 'status-message';
    statusDiv.textContent = '⏳ Yükleniyor...';
    statusDiv.style.display = 'block';
    
    try {
        const response = await fetch(`${API_URL}/voices/upload`, {
            method: 'POST',
            body: formData
        });
        
        const data = await response.json();
        
        if (response.ok) {
            statusDiv.className = 'status-message success';
            statusDiv.textContent = `✅ Başarılı! "${data.filename}" yüklendi.`;
            
            // Form'u temizle
            fileInput.value = '';
            nameInput.value = '';
            descInput.value = '';
            
            // Listeleri yenile
            loadVoices();
            loadCacheInfo();
        } else {
            statusDiv.className = 'status-message error';
            statusDiv.textContent = `❌ Hata: ${data.detail || 'Bilinmeyen hata'}`;
        }
    } catch (error) {
        statusDiv.className = 'status-message error';
        statusDiv.textContent = `❌ Hata: ${error.message}`;
    }
}

// Cache bilgisini yükle
async function loadCacheInfo() {
    try {
        const response = await fetch(`${API_URL}/cache/info`);
        const data = await response.json();
        
        const cacheInfo = document.getElementById('cacheInfo');
        
        const formatBytes = (bytes) => {
            if (bytes === 0) return '0 Bytes';
            const k = 1024;
            const sizes = ['Bytes', 'KB', 'MB', 'GB'];
            const i = Math.floor(Math.log(bytes) / Math.log(k));
            return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
        };
        
        const formatDate = (timestamp) => {
            return new Date(timestamp * 1000).toLocaleString('tr-TR');
        };
        
        cacheInfo.innerHTML = `
            <div class="cache-stats">
                <div class="stat-item">
                    <div class="stat-value">${data.total_cached_embeddings}</div>
                    <div class="stat-label">Cache'lenmiş Embedding</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${data.metadata_entries}</div>
                    <div class="stat-label">Metadata Girişi</div>
                </div>
                <div class="stat-item">
                    <div class="stat-value">${formatBytes(data.cache_files.reduce((sum, f) => sum + f.size, 0))}</div>
                    <div class="stat-label">Toplam Cache Boyutu</div>
                </div>
            </div>
            <div class="cache-files">
                <h3 style="margin-bottom: 10px;">Cache Dosyaları:</h3>
                ${data.cache_files.length > 0 ? data.cache_files.map(file => `
                    <div class="cache-file-item">
                        <span>${file.filename}</span>
                        <span>${formatBytes(file.size)} - ${formatDate(file.modified)}</span>
                    </div>
                `).join('') : '<div style="color: #666; padding: 10px;">Henüz cache dosyası yok</div>'}
            </div>
        `;
    } catch (error) {
        document.getElementById('cacheInfo').innerHTML = 
            `<div style="color: #ef4444;">❌ Hata: ${error.message}</div>`;
    }
}

// Yenileme fonksiyonları
function refreshVoices() {
    loadVoices();
    loadActiveVoice();
}

function refreshCache() {
    loadCacheInfo();
}

