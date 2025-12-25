
import uvicorn
from fastapi import FastAPI, Body, HTTPException, UploadFile, File, Request
from fastapi.responses import FileResponse, JSONResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
import torch
from TTS.api import TTS
import os
import uuid
import hashlib
import pickle
import numpy as np
import json
import shutil
try:
    import soundfile as sf
except ImportError:
    sf = None

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFERENCE_VOICES_DIR = os.path.join(BASE_DIR, "reference_voices")
VOICE_CONFIG_FILE = os.path.join(BASE_DIR, "voice_config.json")
WEB_UI_DIR = os.path.join(BASE_DIR, "web_ui")
PORT = 8020
WEB_UI_PORT = 8696  # Web UI için ayrı port

# Ensure reference voices directory exists
os.makedirs(REFERENCE_VOICES_DIR, exist_ok=True)

app = FastAPI(title="XTTS Local Service")

# CORS ayarları (web UI farklı port'tan erişebilsin diye)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Production'da daha güvenli ayarlayın
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Web UI için static files ve templates
if os.path.exists(WEB_UI_DIR):
    static_dir = os.path.join(WEB_UI_DIR, "static")
    templates_dir = os.path.join(WEB_UI_DIR, "templates")
    if os.path.exists(static_dir):
        app.mount("/static", StaticFiles(directory=static_dir), name="static")
    if os.path.exists(templates_dir):
        templates = Jinja2Templates(directory=templates_dir)
    else:
        templates = None
else:
    templates = None

# Global TTS model
tts = None

@app.on_event("startup")
async def startup_event():
    global tts
    print("Loading XTTS Model... (This requires GPU or strong CPU)")
    
    # Check for MPS (Apple Silicon), then CUDA, then CPU
    if torch.backends.mps.is_available():
        device = "mps"
        print("MPS: Available")
    elif torch.cuda.is_available():
        device = "cuda"
        print("CUDA: Available")
    else:
        device = "cpu"
        print("Using CPU")
    
    # Init TTS - önce model oluştur, sonra device'a taşı
    tts = TTS(model_name="tts_models/multilingual/multi-dataset/xtts_v2")
    tts.to(device)  # ⬅️ kritik satır
    print("XTTS Ready!")

# Use project's ses directory (shared with Docker container via bind mount)
# XTTS runs on host, so use absolute path to project directory
PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_DIR = os.path.join(PROJECT_DIR, "ses")

# Cache directory for speaker embeddings
CACHE_DIR = os.path.join(PROJECT_DIR, ".xtts_cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# Global cache for speaker embeddings: {file_hash: embedding_tensor}
speaker_embedding_cache = {}

def load_voice_config():
    """Load voice configuration from JSON file"""
    if os.path.exists(VOICE_CONFIG_FILE):
        try:
            with open(VOICE_CONFIG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"⚠️  Error loading voice config: {e}, using defaults")
    # Default config
    return {
        "active_voice": "reference.wav",
        "voices": {
            "reference.wav": {
                "name": "Default Voice",
                "path": "reference.wav",
                "description": "Default reference voice"
            }
        }
    }

def save_voice_config(config):
    """Save voice configuration to JSON file"""
    try:
        with open(VOICE_CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(config, f, indent=2, ensure_ascii=False)
        return True
    except Exception as e:
        print(f"❌ Error saving voice config: {e}")
        return False

def get_active_reference_voice():
    """Get the path to the active reference voice file"""
    config = load_voice_config()
    active_voice = config.get("active_voice", "reference.wav")
    
    # Try reference_voices directory first
    voice_path = os.path.join(REFERENCE_VOICES_DIR, active_voice)
    if os.path.exists(voice_path):
        return voice_path
    
    # Try base directory (for backward compatibility)
    voice_path = os.path.join(BASE_DIR, active_voice)
    if os.path.exists(voice_path):
        return voice_path
    
    # Fallback to default
    default_path = os.path.join(BASE_DIR, "reference.wav")
    if os.path.exists(default_path):
        return default_path
    
    raise FileNotFoundError(f"Active reference voice not found: {active_voice}")

def split_text_for_xtts(text: str, max_chars: int = 200) -> list:
    """
    Split text into chunks that XTTS can handle.
    XTTS has a token limit (~400 tokens), which roughly equals ~200-300 characters for Turkish.
    We'll split by sentences first, then by max_chars if needed.
    """
    # First, try to split by sentences (., !, ?, \n)
    import re
    sentences = re.split(r'([.!?]\s+|\n+)', text)
    
    # Combine sentences back with their punctuation
    chunks = []
    current_chunk = ""
    
    for i in range(0, len(sentences), 2):
        sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else "")
        
        # If adding this sentence would exceed limit, save current chunk
        if current_chunk and len(current_chunk) + len(sentence) > max_chars:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
        else:
            current_chunk += sentence
    
    # Add remaining chunk
    if current_chunk.strip():
        chunks.append(current_chunk.strip())
    
    # If any chunk is still too long, split it further
    final_chunks = []
    for chunk in chunks:
        if len(chunk) > max_chars:
            # Split by words
            words = chunk.split()
            current = ""
            for word in words:
                if len(current) + len(word) + 1 > max_chars:
                    if current:
                        final_chunks.append(current.strip())
                    current = word
                else:
                    current += " " + word if current else word
            if current:
                final_chunks.append(current.strip())
        else:
            final_chunks.append(chunk)
    
    return final_chunks if final_chunks else [text[:max_chars]]

def get_file_hash(file_path: str) -> str:
    """Calculate MD5 hash of file for cache key"""
    hash_md5 = hashlib.md5()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hash_md5.update(chunk)
    return hash_md5.hexdigest()

def save_embedding_metadata(file_path: str, file_hash: str, cache_file: str):
    """Save metadata about cached embedding (which file maps to which cache)"""
    metadata_file = os.path.join(CACHE_DIR, "embedding_metadata.json")
    metadata = {}
    
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                metadata = json.load(f)
        except:
            metadata = {}
    
    # Store mapping: file_path -> {hash, cache_file, timestamp}
    metadata[file_path] = {
        "hash": file_hash,
        "cache_file": os.path.basename(cache_file),
        "timestamp": os.path.getmtime(file_path) if os.path.exists(file_path) else 0,
        "file_size": os.path.getsize(file_path) if os.path.exists(file_path) else 0
    }
    
    try:
        with open(metadata_file, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)
    except Exception as e:
        print(f"⚠️  Error saving embedding metadata: {e}")

def get_embedding_metadata():
    """Load embedding metadata to see which files have cached embeddings"""
    metadata_file = os.path.join(CACHE_DIR, "embedding_metadata.json")
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, "r", encoding="utf-8") as f:
                return json.load(f)
        except:
            return {}
    return {}

def get_speaker_embedding(ref_wav: str) -> torch.Tensor:
    """
    Get speaker embedding for reference audio, using cache if available.
    Returns cached embedding or computes and caches it.
    
    Cache Structure:
    - Memory: speaker_embedding_cache[file_hash] = embedding_tensor
    - Disk: .xtts_cache/embedding_{file_hash}.pkl (pickle file)
    - Metadata: .xtts_cache/embedding_metadata.json (maps file_path -> cache info)
    """
    global speaker_embedding_cache
    
    # Calculate file hash for cache key
    file_hash = get_file_hash(ref_wav)
    cache_file = os.path.join(CACHE_DIR, f"embedding_{file_hash}.pth")  # Use .pth for PyTorch format
    
    # Check in-memory cache first
    if file_hash in speaker_embedding_cache:
        print(f"✅ Using in-memory cached embedding for {ref_wav}")
        return speaker_embedding_cache[file_hash]
    
    # Check disk cache - try .pth first (PyTorch format), then .pkl (legacy)
    cache_file_pth = cache_file.replace('.pkl', '.pth')
    
    if os.path.exists(cache_file_pth):
        try:
            embedding = torch.load(cache_file_pth, map_location='cpu')
            speaker_embedding_cache[file_hash] = embedding
            print(f"✅ Loaded cached embedding from disk for {ref_wav} (.pth format)")
            return embedding
        except Exception as e:
            print(f"⚠️  Error loading .pth cache: {e}, trying .pkl...")
    
    # Legacy .pkl support
    if os.path.exists(cache_file):
        try:
            with open(cache_file, "rb") as f:
                embedding = pickle.load(f)
            # Convert back to tensor if needed
            if isinstance(embedding, np.ndarray):
                embedding = torch.from_numpy(embedding)
            speaker_embedding_cache[file_hash] = embedding
            print(f"✅ Loaded cached embedding from disk for {ref_wav} (.pkl format)")
            return embedding
        except Exception as e:
            print(f"⚠️  Error loading cache: {e}, will recompute")
    
    # Compute embedding using XTTS model's low-level API
    print(f"🔄 Computing speaker embedding for {ref_wav} (this may take a moment)...")
    try:
        # Debug: TTS yapısını kontrol et
        print(f"🔍 Debug: tts type: {type(tts)}")
        print(f"🔍 Debug: tts has 'model': {hasattr(tts, 'model')}")
        print(f"🔍 Debug: tts has 'synthesizer': {hasattr(tts, 'synthesizer')}")
        if hasattr(tts, 'synthesizer'):
            print(f"🔍 Debug: synthesizer type: {type(tts.synthesizer)}")
            print(f"🔍 Debug: synthesizer has 'model': {hasattr(tts.synthesizer, 'model')}")
            synth_attrs = [a for a in dir(tts.synthesizer) if not a.startswith('_')]
            print(f"🔍 Debug: synthesizer attributes (first 20): {synth_attrs[:20]}")
            relevant = [a for a in synth_attrs if any(keyword in a.lower() for keyword in ['model', 'tts', 'inference', 'conditioning', 'latent', 'embedding'])]
            print(f"🔍 Debug: synthesizer relevant attributes: {relevant}")
        
        # Try different paths to access the model
        model = None
        model_path = None
        
        # Path 1: tts.model
        if hasattr(tts, 'model'):
            model = tts.model
            model_path = "tts.model"
            print(f"✅ Found model via tts.model, type: {type(model)}")
        # Path 2: tts.synthesizer.tts_model (XTTS uses tts_model, not model)
        elif hasattr(tts, 'synthesizer') and hasattr(tts.synthesizer, 'tts_model'):
            model = tts.synthesizer.tts_model
            model_path = "tts.synthesizer.tts_model"
            print(f"✅ Found model via tts.synthesizer.tts_model, type: {type(model)}")
        # Path 3: tts.synthesizer.model (legacy)
        elif hasattr(tts, 'synthesizer') and hasattr(tts.synthesizer, 'model'):
            model = tts.synthesizer.model
            model_path = "tts.synthesizer.model"
            print(f"✅ Found model via tts.synthesizer.model, type: {type(model)}")
        else:
            print("❌ Could not find model (tried tts.model and tts.synthesizer.model)")
            print(f"🔍 Available tts attributes: {[a for a in dir(tts) if not a.startswith('_')][:15]}")
            return None
        
        print(f"✅ Found model via {model_path}, type: {type(model)}")
        
        # Try get_conditioning_latents
        if hasattr(model, 'get_conditioning_latents'):
            print(f"✅ Using {model_path}.get_conditioning_latents() - low-level API")
            try:
                # get_conditioning_latents returns (gpt_cond_latent, speaker_embedding)
                gpt_cond_latent, speaker_embedding = model.get_conditioning_latents(audio_path=[ref_wav])
                print("✅ Successfully extracted conditioning latents and speaker embedding")
                
                # Create embedding dict
                embedding = {
                    "gpt_cond_latent": gpt_cond_latent,
                    "speaker_embedding": speaker_embedding
                }
                
                # Cache in memory
                speaker_embedding_cache[file_hash] = embedding
                
                # Cache to disk - use torch.save for tensors
                try:
                    # Save as .pth file (PyTorch format)
                    torch.save(embedding, cache_file)
                    print(f"✅ Cached embedding to disk: {cache_file}")
                    
                    # Also save metadata
                    save_embedding_metadata(ref_wav, file_hash, cache_file)
                    print(f"✅ Saved embedding metadata (file: {os.path.basename(ref_wav)}, hash: {file_hash[:8]}...)")
                except Exception as e:
                    print(f"⚠️  Error saving cache: {e} (will continue without disk cache)")
                    import traceback
                    traceback.print_exc()
                
                print(f"✅ Computed and cached embedding for {ref_wav}")
                return embedding
            except Exception as e:
                print(f"❌ {model_path}.get_conditioning_latents() failed: {e}")
                import traceback
                traceback.print_exc()
                return None
        else:
            print(f"❌ {model_path}.get_conditioning_latents() not available")
            print(f"🔍 Available methods: {[m for m in dir(model) if not m.startswith('_') and ('conditioning' in m.lower() or 'latent' in m.lower() or 'embedding' in m.lower())][:10]}")
            return None
        
    except Exception as e:
        print(f"❌ Error computing embedding: {e}")
        raise

@app.post("/tts")
def generate_speech(
    text: str = Body(..., embed=True),
    language: str = Body("tr", embed=True),
    speaker_wav: str = Body(None, embed=True),
    output_filename: str = Body(None, embed=True)  # Optional: specify output filename
):
    try:
        # Ensure shared output directory exists (mounted as volume)
        os.makedirs(OUTPUT_DIR, exist_ok=True)
        
        # Use provided filename or generate one
        if output_filename:
            output_path = os.path.join(OUTPUT_DIR, output_filename)
        else:
            output_path = os.path.join(OUTPUT_DIR, f"output_{uuid.uuid4()}.wav")
        
        # Use provided speaker_wav or get active reference voice from config
        if speaker_wav:
            ref_wav = speaker_wav
        else:
            ref_wav = get_active_reference_voice()
        
        # Check if reference file exists
        if not os.path.exists(ref_wav):
            raise HTTPException(
                status_code=400, 
                detail=f"Reference audio not found at: {ref_wav}"
            )

        # Get or compute speaker embedding (cached)
        # Returns dict with "gpt_cond_latent" and "speaker_embedding" if successful
        latents_dict = get_speaker_embedding(ref_wav)
        
        print(f"Generating TTS for: '{text}' using '{ref_wav}'...")
        print(f"Saving to: {output_path}")
        
        # Use low-level model.inference() if we have cached latents
        if latents_dict is not None and isinstance(latents_dict, dict):
            if "gpt_cond_latent" in latents_dict and "speaker_embedding" in latents_dict:
                print("✅ Using cached latents via tts.model.inference() - FAST PATH!")
                try:
                    # Use model.inference() directly with cached latents
                    # Try different paths to access the model
                    model = None
                    if hasattr(tts, 'model'):
                        model = tts.model
                    elif hasattr(tts, 'synthesizer') and hasattr(tts.synthesizer, 'tts_model'):
                        model = tts.synthesizer.tts_model
                    elif hasattr(tts, 'synthesizer') and hasattr(tts.synthesizer, 'model'):
                        model = tts.synthesizer.model
                    
                    if model is not None and hasattr(model, 'inference'):
                        # Check text length - XTTS has ~400 token limit (~200-300 chars for Turkish)
                        # Split text if too long
                        text_chunks = split_text_for_xtts(text, max_chars=250)
                        
                        if len(text_chunks) > 1:
                            print(f"⚠️  Text too long ({len(text)} chars), splitting into {len(text_chunks)} chunks")
                            # Generate audio for each chunk and concatenate
                            all_wavs = []
                            sample_rate = 24000
                            
                            for i, chunk in enumerate(text_chunks):
                                print(f"  Generating chunk {i+1}/{len(text_chunks)}: '{chunk[:50]}...'")
                                try:
                                    out = model.inference(
                                        text=chunk,
                                        language=language,
                                        gpt_cond_latent=latents_dict["gpt_cond_latent"],
                                        speaker_embedding=latents_dict["speaker_embedding"]
                                    )
                                    all_wavs.append(out["wav"])
                                    sample_rate = out.get("sample_rate", 24000)
                                except Exception as e:
                                    print(f"❌ Error generating chunk {i+1}: {e}")
                                    raise
                            
                            # Concatenate all audio chunks
                            import numpy as np
                            wav = np.concatenate(all_wavs)
                            print(f"✅ Generated {len(text_chunks)} chunks, total length: {len(wav)/sample_rate:.2f}s")
                        else:
                            # Single chunk - normal path
                            out = model.inference(
                                text=text,
                                language=language,
                                gpt_cond_latent=latents_dict["gpt_cond_latent"],
                                speaker_embedding=latents_dict["speaker_embedding"]
                            )
                            wav = out["wav"]
                            sample_rate = out.get("sample_rate", 24000)
                        
                        # Save audio
                        if sf is not None:
                            sf.write(output_path, wav, sample_rate)
                            print(f"✅ Generated using cached embedding (sample_rate: {sample_rate}, duration: {len(wav)/sample_rate:.2f}s)")
                        else:
                            # Fallback: use scipy
                            import scipy.io.wavfile as wavfile
                            wavfile.write(output_path, sample_rate, (wav * 32767).astype(np.int16))
                            print(f"✅ Generated using cached embedding (scipy fallback)")
                    else:
                        raise AttributeError("tts.model.inference() not available")
                except Exception as e:
                    print(f"⚠️  model.inference() failed ({e}), falling back to tts_to_file")
                    import traceback
                    traceback.print_exc()
                    # Fallback to standard method with text splitting
                    text_chunks = split_text_for_xtts(text, max_chars=250)
                    if len(text_chunks) > 1:
                        print(f"⚠️  Text too long, splitting into {len(text_chunks)} chunks for tts_to_file")
                        import numpy as np
                        all_wavs = []
                        sample_rate = 24000
                        for i, chunk in enumerate(text_chunks):
                            chunk_path = output_path.replace('.wav', f'_chunk_{i}.wav')
                            tts.tts_to_file(text=chunk, speaker_wav=ref_wav, language=language, file_path=chunk_path)
                            if sf is not None:
                                wav_data, sr = sf.read(chunk_path)
                                all_wavs.append(wav_data)
                                sample_rate = sr
                            else:
                                import scipy.io.wavfile as wavfile
                                sr, wav_data = wavfile.read(chunk_path)
                                all_wavs.append(wav_data.astype(np.float32) / 32767.0)
                                sample_rate = sr
                            os.remove(chunk_path)
                        wav = np.concatenate(all_wavs)
                        if sf is not None:
                            sf.write(output_path, wav, sample_rate)
                        else:
                            import scipy.io.wavfile as wavfile
                            wavfile.write(output_path, sample_rate, (wav * 32767).astype(np.int16))
                    else:
                        tts.tts_to_file(text=text, speaker_wav=ref_wav, language=language, file_path=output_path)
            else:
                print("⚠️  Invalid latents format, using standard method")
                text_chunks = split_text_for_xtts(text, max_chars=250)
                if len(text_chunks) > 1:
                    print(f"⚠️  Text too long, splitting into {len(text_chunks)} chunks")
                    import numpy as np
                    all_wavs = []
                    sample_rate = 24000
                    for i, chunk in enumerate(text_chunks):
                        chunk_path = output_path.replace('.wav', f'_chunk_{i}.wav')
                        tts.tts_to_file(text=chunk, speaker_wav=ref_wav, language=language, file_path=chunk_path)
                        if sf is not None:
                            wav_data, sr = sf.read(chunk_path)
                            all_wavs.append(wav_data)
                            sample_rate = sr
                        else:
                            import scipy.io.wavfile as wavfile
                            sr, wav_data = wavfile.read(chunk_path)
                            all_wavs.append(wav_data.astype(np.float32) / 32767.0)
                            sample_rate = sr
                        os.remove(chunk_path)
                    wav = np.concatenate(all_wavs)
                    if sf is not None:
                        sf.write(output_path, wav, sample_rate)
                    else:
                        import scipy.io.wavfile as wavfile
                        wavfile.write(output_path, sample_rate, (wav * 32767).astype(np.int16))
                else:
                    tts.tts_to_file(text=text, speaker_wav=ref_wav, language=language, file_path=output_path)
        else:
            # Embedding None ise standard method kullan
            print("⚠️  Using standard tts_to_file method (embedding cache not available)")
            print("⚠️  This will be slower as embedding will be recomputed each time")
            text_chunks = split_text_for_xtts(text, max_chars=250)
            if len(text_chunks) > 1:
                print(f"⚠️  Text too long ({len(text)} chars), splitting into {len(text_chunks)} chunks")
                import numpy as np
                all_wavs = []
                sample_rate = 24000
                for i, chunk in enumerate(text_chunks):
                    print(f"  Generating chunk {i+1}/{len(text_chunks)}: '{chunk[:50]}...'")
                    chunk_path = output_path.replace('.wav', f'_chunk_{i}.wav')
                    tts.tts_to_file(text=chunk, speaker_wav=ref_wav, language=language, file_path=chunk_path)
                    if sf is not None:
                        wav_data, sr = sf.read(chunk_path)
                        all_wavs.append(wav_data)
                        sample_rate = sr
                    else:
                        import scipy.io.wavfile as wavfile
                        sr, wav_data = wavfile.read(chunk_path)
                        all_wavs.append(wav_data.astype(np.float32) / 32767.0)
                        sample_rate = sr
                    os.remove(chunk_path)
                wav = np.concatenate(all_wavs)
                if sf is not None:
                    sf.write(output_path, wav, sample_rate)
                else:
                    import scipy.io.wavfile as wavfile
                    wavfile.write(output_path, sample_rate, (wav * 32767).astype(np.int16))
                print(f"✅ Generated {len(text_chunks)} chunks, total duration: {len(wav)/sample_rate:.2f}s")
            else:
                tts.tts_to_file(text=text, speaker_wav=ref_wav, language=language, file_path=output_path)
        
        print("Generation complete.")
        
        # Return JSON with filename instead of file content (faster, no download needed)
        filename = os.path.basename(output_path)
        return JSONResponse({
            "success": True,
            "filename": filename,
            "path": output_path
        })
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
        # Build 500 error but return detail
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/voices")
def list_voices():
    """List all available reference voices"""
    config = load_voice_config()
    voices = []
    
    # Scan reference_voices directory
    if os.path.exists(REFERENCE_VOICES_DIR):
        for filename in os.listdir(REFERENCE_VOICES_DIR):
            if filename.lower().endswith(('.wav', '.mp3', '.flac')):
                voice_info = config.get("voices", {}).get(filename, {})
                voices.append({
                    "filename": filename,
                    "name": voice_info.get("name", filename),
                    "description": voice_info.get("description", ""),
                    "path": os.path.join(REFERENCE_VOICES_DIR, filename),
                    "is_active": filename == config.get("active_voice")
                })
    
    # Also check base directory for backward compatibility
    for filename in os.listdir(BASE_DIR):
        if filename.lower().endswith(('.wav', '.mp3', '.flac')) and filename not in [v["filename"] for v in voices]:
            voice_info = config.get("voices", {}).get(filename, {})
            voices.append({
                "filename": filename,
                "name": voice_info.get("name", filename),
                "description": voice_info.get("description", ""),
                "path": os.path.join(BASE_DIR, filename),
                "is_active": filename == config.get("active_voice")
            })
    
    return JSONResponse({
        "active_voice": config.get("active_voice"),
        "voices": voices
    })

@app.post("/voices/set-active")
def set_active_voice(voice_filename: str = Body(..., embed=True)):
    """Set the active reference voice"""
    config = load_voice_config()
    
    # Check if voice file exists
    voice_path = os.path.join(REFERENCE_VOICES_DIR, voice_filename)
    if not os.path.exists(voice_path):
        voice_path = os.path.join(BASE_DIR, voice_filename)
        if not os.path.exists(voice_path):
            raise HTTPException(
                status_code=404,
                detail=f"Voice file not found: {voice_filename}"
            )
    
    # Update active voice
    old_active = config.get("active_voice")
    config["active_voice"] = voice_filename
    
    # Add to voices list if not exists
    if voice_filename not in config.get("voices", {}):
        config.setdefault("voices", {})[voice_filename] = {
            "name": voice_filename,
            "path": voice_filename,
            "description": f"Reference voice: {voice_filename}"
        }
    
    if save_voice_config(config):
        # Clear cache for old voice if needed (optional - can keep both cached)
        print(f"✅ Changed active voice from '{old_active}' to '{voice_filename}'")
        return JSONResponse({
            "success": True,
            "message": f"Active voice changed to {voice_filename}",
            "active_voice": voice_filename,
            "old_voice": old_active
        })
    else:
        raise HTTPException(
            status_code=500,
            detail="Failed to save voice configuration"
        )

@app.post("/voices/upload")
async def upload_voice(
    file: UploadFile = File(...),
    name: str = Body(None, embed=True),
    description: str = Body(None, embed=True)
):
    """Upload a new reference voice file"""
    # Validate file type
    if not file.filename.lower().endswith(('.wav', '.mp3', '.flac')):
        raise HTTPException(
            status_code=400,
            detail="Only WAV, MP3, and FLAC files are supported"
        )
    
    # Save file to reference_voices directory
    file_path = os.path.join(REFERENCE_VOICES_DIR, file.filename)
    try:
        with open(file_path, "wb") as f:
            shutil.copyfileobj(file.file, f)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to save file: {str(e)}"
        )
    
    # Update config
    config = load_voice_config()
    config.setdefault("voices", {})[file.filename] = {
        "name": name or file.filename,
        "path": file.filename,
        "description": description or f"Uploaded reference voice: {file.filename}"
    }
    save_voice_config(config)
    
    return JSONResponse({
        "success": True,
        "message": f"Voice file uploaded: {file.filename}",
        "filename": file.filename,
        "path": file_path
    })

@app.get("/voices/active")
def get_active_voice():
    """Get the currently active reference voice"""
    config = load_voice_config()
    active_voice = config.get("active_voice", "reference.wav")
    
    try:
        voice_path = get_active_reference_voice()
        voice_info = config.get("voices", {}).get(active_voice, {})
        
        # Check if embedding is cached (.pth format, fallback to .pkl for legacy)
        file_hash = get_file_hash(voice_path)
        cache_file_pth = os.path.join(CACHE_DIR, f"embedding_{file_hash}.pth")
        cache_file_pkl = os.path.join(CACHE_DIR, f"embedding_{file_hash}.pkl")
        is_cached = os.path.exists(cache_file_pth) or os.path.exists(cache_file_pkl)
        
        return JSONResponse({
            "active_voice": active_voice,
            "path": voice_path,
            "name": voice_info.get("name", active_voice),
            "description": voice_info.get("description", ""),
            "embedding_cached": is_cached,
            "cache_hash": file_hash[:16] if is_cached else None
        })
    except FileNotFoundError as e:
        raise HTTPException(
            status_code=404,
            detail=str(e)
        )

@app.get("/cache/info")
def get_cache_info():
    """Get information about cached embeddings"""
    metadata = get_embedding_metadata()
    cache_files = []
    
    if os.path.exists(CACHE_DIR):
        for filename in os.listdir(CACHE_DIR):
            if filename.startswith("embedding_") and filename.endswith(".pkl"):
                cache_files.append({
                    "filename": filename,
                    "size": os.path.getsize(os.path.join(CACHE_DIR, filename)),
                    "modified": os.path.getmtime(os.path.join(CACHE_DIR, filename))
                })
    
    return JSONResponse({
        "cache_directory": CACHE_DIR,
        "total_cached_embeddings": len(cache_files),
        "metadata_entries": len(metadata),
        "cache_files": cache_files,
        "metadata": metadata
    })

# Web UI Routes
if templates:
    @app.get("/", response_class=HTMLResponse)
    async def web_ui_root(request: Request):
        """Web UI ana sayfası"""
        return templates.TemplateResponse("index.html", {"request": request})
    
    @app.get("/ui", response_class=HTMLResponse)
    async def web_ui(request: Request):
        """Web UI (alternatif route)"""
        return templates.TemplateResponse("index.html", {"request": request})

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
