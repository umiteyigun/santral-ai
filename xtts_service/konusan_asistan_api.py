
import uvicorn
from fastapi import FastAPI, Body, HTTPException
from fastapi.responses import FileResponse, JSONResponse
import torch
from TTS.api import TTS
import os
import uuid

# Configuration
# Default reference voice file: previously doğruluğu test edilmiş sabit dosya.
# İstersen ENV ile REFERENCE_AUDIO verip başka bir WAV kullanabilirsin.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
REFERENCE_AUDIO_PATH = os.getenv(
    "REFERENCE_AUDIO",
    "reference.wav",
)
PORT = 8020

app = FastAPI(title="XTTS Local Service")

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
        
        # Use provided speaker_wav or default
        ref_wav = speaker_wav or REFERENCE_AUDIO_PATH
        
        # Check if reference file exists
        if not os.path.exists(ref_wav):
            raise HTTPException(
                status_code=400, 
                detail=f"Reference audio not found at: {ref_wav}"
            )

        print(f"Generating TTS for: '{text}' using '{ref_wav}'...")
        print(f"Saving to: {output_path}")
        tts.tts_to_file(
            text=text,
            speaker_wav=ref_wav,
            language=language,
            file_path=output_path
        )
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
        # Build 500 error but return detail
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=PORT)
