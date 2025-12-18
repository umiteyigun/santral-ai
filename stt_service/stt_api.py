"""
STT Service - FasterWhisper API
Harici servis olarak çalışır, agent'tan HTTP istekleri alır
"""

import uvicorn
from fastapi import FastAPI, Body, HTTPException, UploadFile, File
from fastapi.responses import JSONResponse
from faster_whisper import WhisperModel
import os
import tempfile

PORT = 8030
MODEL_SIZE = os.getenv("WHISPER_MODEL", "small")  # small, base, tiny
DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")

app = FastAPI(title="STT Service - FasterWhisper")

# Global model
stt_model = None

@app.on_event("startup")
async def startup_event():
    global stt_model
    print(f"Loading Whisper STT model ({MODEL_SIZE}, {DEVICE})...")
    try:
        stt_model = WhisperModel(MODEL_SIZE, device=DEVICE, compute_type=COMPUTE_TYPE)
        print("✅ Whisper STT model loaded successfully")
    except Exception as e:
        print(f"❌ Error loading Whisper model: {e}")
        raise

@app.post("/transcribe")
async def transcribe_audio(
    language: str = Body("tr", embed=True),
    audio_file: UploadFile = File(...)
):
    """Transcribe audio file to text"""
    try:
        if stt_model is None:
            raise HTTPException(status_code=503, detail="STT model not loaded")
        
        # Save uploaded file to temp location
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as tmp_file:
            tmp_path = tmp_file.name
            content = await audio_file.read()
            tmp_file.write(content)
        
        try:
            # Transcribe
            print(f"Transcribing audio file: {tmp_path}")
            segments, info = stt_model.transcribe(tmp_path, language=language)
            segment_list = list(segments)
            text = " ".join([seg.text for seg in segment_list])
            
            print(f"Transcription result: '{text}' ({len(segment_list)} segments)")
            
            return JSONResponse({
                "text": text,
                "language": info.language,
                "language_probability": info.language_probability,
                "segments": len(segment_list)
            })
        finally:
            # Clean up temp file
            if os.path.exists(tmp_path):
                os.remove(tmp_path)
                
    except Exception as e:
        print(f"Error transcribing: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health():
    """Health check"""
    return {
        "status": "ok",
        "model_loaded": stt_model is not None,
        "model_size": MODEL_SIZE,
        "device": DEVICE
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)

