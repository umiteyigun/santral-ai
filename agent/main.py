"""
LiveKit Voice Agent
- Listens to user audio (STT with FasterWhisper)
- Gets response from Ollama (local LLM)
- Generates speech with XTTS (local TTS)
- Streams audio back to user
"""

import asyncio
import logging
import os
import wave
import uuid
import requests
import webrtcvad
import json
import base64
from datetime import datetime
from livekit import rtc
from livekit.agents import JobContext, WorkerOptions, cli

# #region debug logging
DEBUG_LOG_PATH = "/app/.cursor/debug.log"
def debug_log(location, message, data=None, hypothesis_id=None):
    try:
        os.makedirs(os.path.dirname(DEBUG_LOG_PATH), exist_ok=True)
        with open(DEBUG_LOG_PATH, "a") as f:
            log_entry = {
                "id": f"log_{int(datetime.now().timestamp() * 1000)}_{uuid.uuid4().hex[:8]}",
                "timestamp": int(datetime.now().timestamp() * 1000),
                "location": location,
                "message": message,
                "data": data or {},
                "sessionId": "debug-session",
                "runId": "run1",
                "hypothesisId": hypothesis_id
            }
            f.write(json.dumps(log_entry) + "\n")
        # Also log to stdout for docker logs
        logger.info(f"[DEBUG] {location}: {message} {json.dumps(data or {})}")
    except Exception as e:
        logger.error(f"[DEBUG] Log error: {e}")
# #endregion

# ===== CONFIGURATION =====
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://host.docker.internal:11434/api/generate")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "ytagalar/trendyol-llm-7b-chat-dpo-v1.0-gguf:latest")
XTTS_API_URL = os.getenv("XTTS_API_URL", "http://host.docker.internal:8020/tts")
STT_API_URL = os.getenv("STT_API_URL", "http://stt-service:8030/transcribe")
WEB_API_URL = os.getenv("WEB_API_URL", "http://web-ui:3000/api/agent-message")

SAMPLE_RATE = 16000
CHANNELS = 1
VAD_MODE = 3  # Aggressive
FRAME_DURATION_MS = 30
CHUNK_SIZE_BYTES = int(SAMPLE_RATE * FRAME_DURATION_MS / 1000) * 2  # 960 bytes

# ===== LOGGING =====
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

# ===== GLOBAL MODELS =====
# STT model removed - now using external STT service

# ===== API CALLS =====

async def call_stt(audio_file: str) -> str:
    """Call external STT service"""
    try:
        logger.info(f"📞 Calling STT service: {STT_API_URL}")
        # Run blocking request in executor to avoid blocking event loop
        import concurrent.futures
        loop = asyncio.get_event_loop()
        
        def _make_request():
            with open(audio_file, 'rb') as f:
                files = {'audio_file': (os.path.basename(audio_file), f, 'audio/wav')}
                data = {'language': 'tr'}
                response = requests.post(STT_API_URL, files=files, data=data, timeout=60)
                response.raise_for_status()
                return response.json()
        
        result = await loop.run_in_executor(None, _make_request)
        text = result.get("text", "").strip()
        logger.info(f"✅ STT completed: '{text}' (length: {len(text)})")
        return text
    except Exception as e:
        logger.error(f"❌ STT error: {e}", exc_info=True)
        return ""

async def call_ollama(user_text: str) -> str:
    """Call local Ollama LLM API"""
    try:
        logger.info(f"🤖 [call_ollama] Starting - URL: {OLLAMA_URL}, text length: {len(user_text)}")
        # Run blocking request in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        
        def _make_ollama_request():
            logger.info(f"🤖 [call_ollama] Making HTTP POST request...")
            resp = requests.post(
                OLLAMA_URL,
                json={
            "model": OLLAMA_MODEL,
                    "prompt": user_text,
            "stream": False
                },
                timeout=30
            )
            logger.info(f"🤖 [call_ollama] HTTP response status: {resp.status_code}")
            resp.raise_for_status()
            return resp.json()
        
        logger.info(f"🤖 [call_ollama] Running in executor...")
        data = await loop.run_in_executor(None, _make_ollama_request)
        response_text = data.get("response", "Üzgünüm, cevap veremedim.")
        logger.info(f"🤖 [call_ollama] Response received: {len(response_text)} chars")
        return response_text
    except Exception as e:
        logger.error(f"❌ [call_ollama] Ollama error: {e}", exc_info=True)
        return "Üzgünüm, bir hata oluştu."

async def call_xtts(text: str, output_file: str) -> bool:
    """Call local XTTS API - file is saved directly to shared ses/ directory"""
    try:
        # Extract filename from output_file path (e.g., /app/ses/response_xxx.wav -> response_xxx.wav)
        output_filename = os.path.basename(output_file)
        logger.info(f"🔊 [call_xtts] Starting - API: {XTTS_API_URL}, text length: {len(text)}, output: {output_file}")
        
        # Run blocking request in executor to avoid blocking event loop
        loop = asyncio.get_event_loop()
        logger.info(f"🔊 [call_xtts] Got event loop, creating executor task...")
        
        def _make_xtts_request():
            logger.info(f"🔊 [call_xtts] _make_xtts_request: Making HTTP POST to {XTTS_API_URL}")
            resp = requests.post(
                XTTS_API_URL,
                json={
                    "text": text,
                    "language": "tr",
                    "output_filename": output_filename  # Tell XTTS what filename to use
                },
                timeout=180  # Increased timeout for XTTS (can take 1-2 minutes)
            )
            logger.info(f"🔊 [call_xtts] HTTP response status: {resp.status_code}")
            resp.raise_for_status()
            result = resp.json()
            logger.info(f"🔊 [call_xtts] Response: {result}")
            return result.get("filename")
        
        logger.info(f"🔊 [call_xtts] Running in executor...")
        saved_filename = await loop.run_in_executor(None, _make_xtts_request)
        logger.info(f"✅ [call_xtts] XTTS API response received: filename={saved_filename}")
        
        # File is already saved to ses/ directory by XTTS service
        # Just verify it exists at the expected path
        if saved_filename and os.path.exists(output_file):
            logger.info(f"✅ [call_xtts] File exists at: {output_file}")
            return True
        else:
            logger.error(f"❌ [call_xtts] File not found at: {output_file}")
            return False
    except Exception as e:
        logger.error(f"❌ [call_xtts] XTTS error: {e}", exc_info=True)
        import traceback
        logger.error(f"❌ [call_xtts] Traceback: {traceback.format_exc()}")
        return False

# ===== VOICE AGENT =====

class VoiceAgent:
    def __init__(self, ctx: JobContext):
        self.ctx = ctx
        self.vad = webrtcvad.Vad(VAD_MODE)
        self.audio_source = None
        self.audio_track = None
        self.track_states = {}  # track_id -> {is_speaking, silence_count, frames}
        self.greeting_sent = False  # Track if greeting has been sent
        self.greeting_cooldown_file = "/tmp/greeting_cooldown.json"  # Track greeting cooldown across agent instances
        self.greeting_cooldown_seconds = 30  # Don't send greeting if one was sent in last 30 seconds
        self.data_channel = None  # Data channel for sending messages to web
        self.is_playing_audio = False  # Track if audio is currently playing (disable microphone during playback)

    async def start(self):
        """Initialize and connect to room"""
        # #region debug log
        debug_log("agent/main.py:97", "VoiceAgent.start called", {
            "room_name": self.ctx.room.name if self.ctx.room else None
        }, "H3")
        # #endregion
        logger.info(f"🚀 Starting agent for room: {self.ctx.room.name}")
        logger.info(f"📡 STT Service: {STT_API_URL}")
        logger.info(f"📡 XTTS Service: {XTTS_API_URL}")
        logger.info(f"📡 Ollama: {OLLAMA_URL}")
        
        await self.ctx.connect()
        # #region debug log
        debug_log("agent/main.py:102", "ctx.connect completed", {}, "H3")
        # #endregion
        logger.info("✅ Connected to room")
        
        # Create audio source and track for playback
        self.audio_source = rtc.AudioSource(24000, CHANNELS)  # 24000Hz to match XTTS output
        self.audio_track = rtc.LocalAudioTrack.create_audio_track("agent_voice", self.audio_source)
        await self.ctx.room.local_participant.publish_track(self.audio_track)
        logger.info("✅ Published agent audio track")
        
        self.ctx.room.on("participant_connected")(self._on_participant_connected)
        self.ctx.room.on("track_published")(self._on_track_published)
        self.ctx.room.on("track_subscribed")(self._on_track_subscribed)
        
        # Check if there are already users in the room (before we connected)
        existing_users = [
            p for p in self.ctx.room.remote_participants.values()
            if not p.identity.startswith("agent-")
        ]
        
        # Check if there are other agents already in the room
        existing_agents = [
            p for p in self.ctx.room.remote_participants.values()
            if p.identity.startswith("agent-")
        ]
        
        logger.info(f"📊 Room state: {len(existing_users)} users, {len(existing_agents)} other agents")
        logger.info(f"🔍 Debug: audio_source={self.audio_source is not None}, existing_users={len(existing_users)}, existing_agents={len(existing_agents)}")
        
        # If there are already users in the room when agent connects, send greeting
        # (This handles the case where user connected before agent)
        # SIP çağrıları için: Kullanıcı varsa greeting gönder (diğer agent'ları görmezden gel)
        if existing_users:
            logger.info(f"👋 Users already in room when agent connected, sending greeting...")
            if self._should_send_greeting():
                logger.info(f"✅ Greeting check passed, sending greeting...")
                # Don't set greeting_sent here - set it after greeting is successfully sent
                asyncio.create_task(self._send_greeting())
            else:
                logger.info("⏸️ Greeting cooldown active, skipping")
        else:
            logger.info(f"⚠️ Greeting condition not met: existing_users={len(existing_users) if existing_users else 0}, existing_agents={len(existing_agents)}")
            # If no users yet, wait a bit and check again (user might be connecting)
            if not existing_users:
                logger.info("⏳ No users in room yet, will greet when user connects...")
        
        for participant in self.ctx.room.remote_participants.values():
            await self._handle_participant(participant)
        
        logger.info("👂 Agent ready, listening for audio...")

    async def _handle_participant(self, participant: rtc.RemoteParticipant):
        """Subscribe to participant's audio tracks"""
        logger.info(f"👤 Handling participant: {participant.identity}")
        for publication in participant.track_publications.values():
            if publication.kind == rtc.TrackKind.KIND_AUDIO:
                await self._subscribe_to_audio(publication, participant)

    async def _subscribe_to_audio(self, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        """Subscribe to an audio track"""
        try:
            if not publication.subscribed:
                publication.set_subscribed(True)
                logger.info(f"🔔 Subscribed to audio from {participant.identity}")
            
            track = publication.track
            if track is not None:
                logger.info(f"✅ Track already available, processing: {participant.identity}")
                asyncio.create_task(self._process_audio_stream(track, participant.identity))
            else:
                logger.info(f"⏳ Track not available yet, waiting for track_subscribed event: {participant.identity}")
        except Exception as e:
            logger.error(f"❌ Error subscribing to track: {e}", exc_info=True)

    def _on_participant_connected(self, participant: rtc.RemoteParticipant):
        """Called when participant joins"""
        logger.info(f"👋 Participant connected: {participant.identity}")
        asyncio.create_task(self._handle_participant(participant))
        
        # Send greeting when user (not agent) connects, only if:
        # 1. We haven't sent greeting yet
        # 2. We are already connected to the room (start() completed)
        if not participant.identity.startswith("agent-") and not self.greeting_sent:
            logger.info(f"🔍 User connected check: greeting_sent={self.greeting_sent}")
            
            # Send greeting (no need to wait for audio_source since we use data channel)
            if self._should_send_greeting():
                logger.info(f"👋 User connected, sending greeting...")
                # Don't set greeting_sent here - set it after greeting is successfully sent
                asyncio.create_task(self._send_greeting())
            else:
                logger.info("⏸️ Greeting cooldown active, skipping")
        elif participant.identity.startswith("agent-"):
            logger.info(f"👋 Agent participant connected, skipping greeting")
        else:
            logger.info(f"👋 User already greeted (greeting_sent={self.greeting_sent}), skipping")

    def _on_track_published(self, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        """Called when track is published"""
        if publication.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"📢 Audio track published by {participant.identity}")
            asyncio.create_task(self._subscribe_to_audio(publication, participant))

    def _on_track_subscribed(self, track: rtc.Track, publication: rtc.TrackPublication, participant: rtc.RemoteParticipant):
        """Called when track is subscribed"""
        if track.kind == rtc.TrackKind.KIND_AUDIO:
            logger.info(f"🎧 Audio track subscribed from {participant.identity}")
            asyncio.create_task(self._process_audio_stream(track, participant.identity))

    async def _process_audio_stream(self, track: rtc.AudioTrack, participant_id: str):
        """Process incoming audio stream with VAD"""
        logger.info(f"[DEBUG] _process_audio_stream called: participant={participant_id}, track_sid={track.sid}")
        try:
            # #region debug log
            debug_log("agent/main.py:191", "_process_audio_stream called", {"participant_id": participant_id, "track_sid": str(track.sid)}, "H5")
            # #endregion
        except Exception as e:
            logger.error(f"Debug log error: {e}", exc_info=True)
        
        stream = rtc.AudioStream(track)
        track_id = track.sid
        
        logger.info(f"[DEBUG] AudioStream created: track_id={track_id}, participant_id={participant_id}")
        try:
            # #region debug log
            debug_log("agent/main.py:197", "AudioStream created", {"track_id": str(track_id), "participant_id": participant_id}, "H5")
            # #endregion
        except Exception as e:
            logger.error(f"Debug log error: {e}", exc_info=True)
        
        logger.info(f"🎤 Processing audio stream from {participant_id} (track: {track_id})")
        
        resampler = None
        frame_buffer = []  # Buffer frames before resampling
        audio_buffer = bytearray()  # Buffer resampled audio data for VAD
        self.track_states[track_id] = {
            'is_speaking': False,
            'silence_count': 0,
            'frames': [],
            'participant_id': participant_id  # Store participant_id for audio level logging
        }
        
        # #region debug log
        debug_log("agent/main.py:207", "Track state initialized", {"track_id": track_id}, "H5")
        # #endregion
        
        try:
            # #region debug log
            debug_log("agent/main.py:211", "Starting audio stream loop", {"track_id": track_id, "participant_id": participant_id}, "H5")
            # #endregion
            frame_count = 0
            async for frame_event in stream:
                frame_count += 1
                frame = frame_event.frame
                state = self.track_states[track_id]
                
                # #region debug log
                if frame_count % 100 == 0:  # Log every 100 frames to avoid spam
                    debug_log("agent/main.py:213", "Audio frame received", {"track_id": track_id, "frame_count": frame_count, "sample_rate": frame.sample_rate, "num_channels": frame.num_channels, "data_len": len(frame.data), "samples_per_channel": frame.samples_per_channel}, "H4")
                # #endregion
                
                # Initialize resampler on first frame if needed
                if resampler is None and (frame.sample_rate != SAMPLE_RATE or frame.num_channels != CHANNELS):
                    resampler = rtc.AudioResampler(
                        input_rate=frame.sample_rate,
                        output_rate=SAMPLE_RATE,
                        num_channels=CHANNELS
                    )
                    logger.info(f"🔄 Resampler: {frame.sample_rate}Hz/{frame.num_channels}ch -> {SAMPLE_RATE}Hz/{CHANNELS}ch")
                    # #region debug log
                    debug_log("agent/main.py:218", "Resampler initialized", {"input_rate": frame.sample_rate, "output_rate": SAMPLE_RATE, "input_channels": frame.num_channels, "output_channels": CHANNELS}, "H4")
                    # #endregion
                
                # Resample if needed, otherwise use frame directly
                if resampler:
                    # Buffer frames and push in batches to help resampler fill internal buffer
                    frame_buffer.append(frame)
                    
                    # Push every 10 frames to help resampler fill internal buffer
                    if len(frame_buffer) >= 10:
                        try:
                            # Push all buffered frames
                            all_resampled = []
                            for buffered_frame in frame_buffer:
                                resampled_frames = resampler.push(buffered_frame)
                                all_resampled.extend(resampled_frames)
                            
                            # #region debug log
                            if frame_count % 100 == 0:
                                debug_log("agent/main.py:232", "Resampler push result (batched)", {"resampled_frame_count": len(all_resampled), "buffered_frame_count": len(frame_buffer), "track_id": track_id, "frame_count": frame_count}, "H4")
                            # #endregion
                            
                            # Process resampled frames - accumulate data for VAD
                            for resampled_frame in all_resampled:
                                audio_buffer.extend(resampled_frame.data)
                            
                            # Process audio buffer in VAD-sized chunks
                            while len(audio_buffer) >= CHUNK_SIZE_BYTES:
                                chunk = bytes(audio_buffer[:CHUNK_SIZE_BYTES])
                                audio_buffer = audio_buffer[CHUNK_SIZE_BYTES:]
                                await self._process_audio_chunk(chunk, track_id)
                            
                            # Clear buffer
                            frame_buffer = []
                            
                            # If still no frames, try flushing
                            if len(all_resampled) == 0 and frame_count % 100 == 0:
                                try:
                                    flushed_frames = resampler.flush()
                                    if len(flushed_frames) > 0:
                                        # #region debug log
                                        debug_log("agent/main.py:240", "Resampler flush returned frames", {"flushed_frame_count": len(flushed_frames), "track_id": track_id, "frame_count": frame_count}, "H4")
                                        # #endregion
                                        for resampled_frame in flushed_frames:
                                            audio_buffer.extend(resampled_frame.data)
                                        
                                        # Process audio buffer in VAD-sized chunks
                                        while len(audio_buffer) >= CHUNK_SIZE_BYTES:
                                            chunk = bytes(audio_buffer[:CHUNK_SIZE_BYTES])
                                            audio_buffer = audio_buffer[CHUNK_SIZE_BYTES:]
                                            await self._process_audio_chunk(chunk, track_id)
                                except Exception as flush_error:
                                    # #region debug log
                                    debug_log("agent/main.py:247", "Resampler flush error", {"error": str(flush_error), "track_id": track_id}, "H4")
                                    # #endregion
                                    pass
                        except Exception as e:
                            logger.error(f"❌ Resampler error: {e}")
                            # #region debug log
                            debug_log("agent/main.py:256", "Resampler error, using original frames", {"error": str(e), "track_id": track_id}, "H4")
                            # #endregion
                            # Fallback: use frames directly (shouldn't happen often)
                            for buffered_frame in frame_buffer:
                                # For fallback, we need to resample manually or skip resampling
                                # For now, skip these frames to avoid errors
                                pass
                            frame_buffer = []
                else:
                    await self._process_audio_chunk(frame.data, track_id)
                    
        except Exception as e:
            logger.error(f"❌ Error processing audio stream: {e}", exc_info=True)
            # #region debug log
            debug_log("agent/main.py:250", "Error in audio stream processing", {"error": str(e), "track_id": track_id, "participant_id": participant_id}, "H5")
            # #endregion
        finally:
            # #region debug log
            debug_log("agent/main.py:255", "Audio stream loop ended", {"track_id": track_id, "participant_id": participant_id}, "H5")
            # #endregion
            if track_id in self.track_states:
                del self.track_states[track_id]
                logger.info(f"🧹 Cleaned up state for track {track_id}")

    async def _process_audio_chunk(self, data: bytes, track_id: str):
        """Process audio chunk with VAD"""
        # Don't process audio while agent is playing audio
        if self.is_playing_audio:
            return
        
        state = self.track_states.get(track_id)
        if not state:
            # #region debug log
            debug_log("agent/main.py:243", "No state for track_id, skipping chunk", {"track_id": track_id}, "H4")
            # #endregion
            return
        
        participant_id = state.get('participant_id', '')

        # Process in 30ms chunks for VAD
        for i in range(0, len(data), CHUNK_SIZE_BYTES):
            chunk = data[i:i+CHUNK_SIZE_BYTES]
            if len(chunk) < CHUNK_SIZE_BYTES:
                # #region debug log
                debug_log("agent/main.py:252", "Incomplete chunk, skipping", {"chunk_len": len(chunk), "expected": CHUNK_SIZE_BYTES, "track_id": track_id}, "H4")
                # #endregion
                break
            
            try:
                # Calculate audio level for debugging (RMS - Root Mean Square)
                import struct
                samples = struct.unpack(f'<{len(chunk)//2}h', chunk)
                rms = (sum(s*s for s in samples) / len(samples)) ** 0.5
                max_amplitude = max(abs(s) for s in samples) if samples else 0
                
                is_speech = self.vad.is_speech(chunk, SAMPLE_RATE)
                # #region debug log
                debug_log("agent/main.py:258", "VAD result", {"is_speech": is_speech, "chunk_len": len(chunk), "track_id": track_id, "is_speaking": state['is_speaking'], "silence_count": state['silence_count'], "rms": int(rms), "max_amplitude": max_amplitude}, "H4")
                # #endregion
                
                # Log audio level every 100 chunks for SIP participants
                if participant_id and "sip_" in participant_id:
                    if not hasattr(self, '_chunk_count'):
                        self._chunk_count = {}
                    if track_id not in self._chunk_count:
                        self._chunk_count[track_id] = 0
                    self._chunk_count[track_id] += 1
                    if self._chunk_count[track_id] % 100 == 0:
                        logger.info(f"🔊 Audio level check (SIP): track={track_id}, participant={participant_id}, rms={int(rms)}, max={max_amplitude}, is_speech={is_speech}")
            except Exception as e:
                logger.error(f"❌ VAD error: {e}")
                # #region debug log
                debug_log("agent/main.py:263", "VAD error", {"error": str(e), "track_id": track_id}, "H4")
                # #endregion
                continue
            
            if is_speech:
                if not state['is_speaking']:
                    logger.info(f"🗣️ Speech detected on track {track_id}")
                    # #region debug log
                    debug_log("agent/main.py:269", "Speech started", {"track_id": track_id}, "H4")
                    # #endregion
                state['is_speaking'] = True
                state['silence_count'] = 0
                state['frames'].append(chunk)
            else:
                if state['is_speaking']:
                    state['silence_count'] += 1
                    state['frames'].append(chunk)
                    
                    # After 500ms of silence, process speech (faster response)
                    if state['silence_count'] >= 17:  # ~500ms at 30ms chunks
                        logger.info(f"🎙️ Processing speech from track {track_id} ({len(state['frames'])} chunks)")
                        # #region debug log
                        debug_log("agent/main.py:282", "Silence threshold reached, processing speech", {"track_id": track_id, "frame_count": len(state['frames']), "total_bytes": sum(len(f) for f in state['frames'])}, "H4")
                        # #endregion
                        await self._handle_speech(b''.join(state['frames']), track_id)
                        state['frames'] = []
                        state['is_speaking'] = False
                        state['silence_count'] = 0
                else:
                    # #region debug log
                    debug_log("agent/main.py:290", "No speech, clearing buffer", {"track_id": track_id}, "H4")
                    # #endregion
                    state['silence_count'] = 0
                    state['frames'] = []

    async def _handle_speech(self, audio_data: bytes, track_id: str):
        """Handle detected speech: STT -> LLM -> TTS -> Playback"""
        # Don't process speech until greeting is sent
        if not self.greeting_sent:
            logger.debug(f"⏸️ Skipping speech processing - greeting not sent yet")
            return
        
        # Don't process speech while audio is playing
        if self.is_playing_audio:
            logger.debug(f"⏸️ Skipping speech processing - audio is currently playing")
            return
        
        # #region debug log
        debug_log("agent/main.py:295", "Handling speech", {"track_id": track_id, "audio_data_len": len(audio_data)}, "H4")
        # #endregion
        try:
            logger.info("🎙️ Processing speech...")
            
            # Save audio to temp file for STT
            temp_wav = f"/tmp/speech_{uuid.uuid4()}.wav"
            with wave.open(temp_wav, 'wb') as wf:
                wf.setnchannels(CHANNELS)
                wf.setsampwidth(2)
                wf.setframerate(SAMPLE_RATE)
                wf.writeframes(audio_data)

            # #region debug log
            debug_log("agent/main.py:308", "Audio saved to temp file", {"temp_wav": temp_wav, "audio_data_len": len(audio_data)}, "H4")
            # #endregion
            
            # STT - Call external STT service
            logger.info("📝 Transcribing via STT service...")
            # #region debug log
            debug_log("agent/main.py:313", "Starting STT", {"temp_wav": temp_wav}, "H4")
            # #endregion
            text = await call_stt(temp_wav)
            logger.info(f"📝 Transcribed: '{text}' (length: {len(text)})")
            
            # Save transcribed text to file for debugging
            transcript_file = "/tmp/user_transcripts.txt"
            try:
                with open(transcript_file, "a", encoding="utf-8") as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"[{timestamp}] {text}\n")
                logger.info(f"💾 Saved transcript to {transcript_file}")
            except Exception as e:
                logger.error(f"❌ Error saving transcript: {e}")
            
            # #region debug log
            debug_log("agent/main.py:319", "STT completed", {"user_text": text}, "H4")
            # #endregion
            
            if not text.strip():
                logger.warning("⚠️ Empty transcription, skipping...")
                if os.path.exists(temp_wav):
                    os.remove(temp_wav)
                return

            # LLM
            logger.info(f"🤖 Sending to Ollama: {text}")
            response_text = await call_ollama(text)
            logger.info(f"🤖 Ollama response: {response_text}")

            # Save conversation to file for debugging
            conversation_file = "/tmp/conversation_log.txt"
            try:
                with open(conversation_file, "a", encoding="utf-8") as f:
                    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                    f.write(f"\n[{timestamp}]\n")
                    f.write(f"Kullanıcı: {text}\n")
                    f.write(f"Asistan: {response_text}\n")
                    f.write("-" * 80 + "\n")
                logger.info(f"💾 Saved conversation to {conversation_file}")
            except Exception as e:
                logger.error(f"❌ Error saving conversation: {e}")
        
            # TTS
            logger.info("🔊 Generating speech...")
            try:
                # Use shared ses/ directory (mounted from host, accessible to both XTTS and agent)
                output_wav = f"/app/ses/response_{uuid.uuid4()}.wav"
                logger.info(f"📁 Output WAV path: {output_wav}")
                logger.info(f"📞 About to call call_xtts with text length: {len(response_text)}")
                logger.info(f"📞 XTTS_API_URL: {XTTS_API_URL}")
                success = await call_xtts(response_text, output_wav)
                logger.info(f"📞 call_xtts returned: success={success}")
            except Exception as tts_error:
                logger.error(f"❌ Error in TTS section: {tts_error}", exc_info=True)
                import traceback
                logger.error(f"❌ TTS Traceback: {traceback.format_exc()}")
                success = False
                output_wav = None
            
            if success and os.path.exists(output_wav):
                logger.info(f"✅ TTS file created: {output_wav}")
                try:
                    file_size = os.path.getsize(output_wav)
                    logger.info(f"📊 TTS file size: {file_size} bytes")
                except Exception as size_error:
                    logger.error(f"❌ Error getting file size: {size_error}")
                    file_size = 0
                
                # Play audio through LiveKit audio track
                try:
                    logger.info(f"🔊 Playing audio file: {output_wav}")
                    if self.audio_source is None:
                        logger.error("❌ audio_source is None, cannot play audio")
                    else:
                        await self._play_audio(output_wav)
                        logger.info(f"✅ Audio playback completed")
                except Exception as e:
                    logger.error(f"❌ Error playing audio: {e}", exc_info=True)
                    import traceback
                    logger.error(f"❌ Traceback: {traceback.format_exc()}")
                finally:
                    # Also send to web client for UI display (optional)
                    try:
                        logger.info(f"📤 Sending message to web client...")
                        await self._send_message_to_web(text, response_text, output_wav)
                        logger.info(f"✅ Response sent to web client")
                    except Exception as web_error:
                        logger.warning(f"⚠️ Failed to send to web client: {web_error}")
                    
                    # Clean up temp file - DISABLED: Keep files for debugging agent count
                    # if os.path.exists(output_wav):
                    #     os.remove(output_wav)
                    #     logger.info(f"🗑️ Removed temp file: {output_wav}")
                    logger.info(f"💾 Keeping response file for debugging: {output_wav}")
            else:
                logger.error(f"❌ Failed to generate speech: success={success}, exists={os.path.exists(output_wav) if output_wav else False}")
            
            os.remove(temp_wav)
            
        except Exception as e:
            logger.error(f"❌ Error handling speech: {e}", exc_info=True)

    def _should_send_greeting(self) -> bool:
        """Check if greeting should be sent (cooldown mechanism to prevent greeting on refresh)"""
        try:
            if not os.path.exists(self.greeting_cooldown_file):
                return True  # No cooldown file, can send greeting
            
            with open(self.greeting_cooldown_file, 'r') as f:
                data = json.load(f)
                last_greeting_time = data.get('last_greeting_time', 0)
                cooldown_seconds = data.get('cooldown_seconds', self.greeting_cooldown_seconds)
                
                current_time = datetime.now().timestamp()
                time_since_last_greeting = current_time - last_greeting_time
                
                if time_since_last_greeting >= cooldown_seconds:
                    return True  # Cooldown expired, can send greeting
                else:
                    logger.info(f"⏸️ Greeting cooldown active ({int(cooldown_seconds - time_since_last_greeting)}s remaining), skipping")
                    return False  # Still in cooldown
        except Exception as e:
            logger.error(f"❌ Error checking greeting cooldown: {e}")
            return True  # On error, allow greeting (fail open)
    
    def _update_greeting_cooldown(self):
        """Update greeting cooldown timestamp"""
        try:
            os.makedirs(os.path.dirname(self.greeting_cooldown_file), exist_ok=True)
            with open(self.greeting_cooldown_file, 'w') as f:
                json.dump({
                    'last_greeting_time': datetime.now().timestamp(),
                    'cooldown_seconds': self.greeting_cooldown_seconds
                }, f)
        except Exception as e:
            logger.error(f"❌ Error updating greeting cooldown: {e}")

    async def _send_greeting(self):
        """Send greeting message when agent joins room"""
        try:
            # Check cooldown before sending
            if not self._should_send_greeting():
                logger.info("⏸️ Skipping greeting due to cooldown")
                return
            
            greeting_text = " Merhaba. Size nasıl yardımcı olabilirim ?"
            logger.info(f"👋 Sending greeting: {greeting_text}")
            
            # Generate speech with XTTS
            # Use shared ses/ directory (mounted from host, accessible to both XTTS and agent)
            output_wav = f"/app/ses/greeting_{uuid.uuid4()}.wav"
            logger.info(f"🔊 Generating greeting speech...")
            success = await call_xtts(greeting_text, output_wav)
            
            if success and os.path.exists(output_wav):
                logger.info(f"✅ Greeting TTS file created: {output_wav}")
                # Play greeting audio through LiveKit
                try:
                    logger.info(f"🔊 Playing greeting audio: {output_wav}")
                    if self.audio_source is None:
                        logger.error("❌ audio_source is None, cannot play greeting")
                    else:
                        await self._play_audio(output_wav)
                        logger.info("✅ Greeting audio playback completed")
                except Exception as play_error:
                    logger.error(f"❌ Error playing greeting: {play_error}", exc_info=True)
                
                # Also send to web client for UI display (optional)
                try:
                    await self._send_message_to_web("", greeting_text, output_wav)
                    logger.info("✅ Greeting message sent to web")
                except Exception as send_error:
                    logger.warning(f"⚠️ Failed to send greeting to web: {send_error}")
                
                # Clean up
                if os.path.exists(output_wav):
                    os.remove(output_wav)
                
                self._update_greeting_cooldown()  # Update cooldown after successful greeting
                self.greeting_sent = True  # Enable microphone listening after greeting is sent
                logger.info("✅ Greeting sent successfully - microphone now enabled")
            else:
                logger.error(f"❌ Failed to generate greeting speech: success={success}, file_exists={os.path.exists(output_wav) if output_wav else False}")
        except Exception as e:
            logger.error(f"❌ Error sending greeting: {e}", exc_info=True)

    async def _play_audio(self, wav_file: str):
        """Play audio file through audio source - stream in 10ms chunks for WebRTC compatibility"""
        if self.audio_source is None:
            logger.error(f"❌ Cannot play audio: audio_source is None")
            return
        
        if not os.path.exists(wav_file):
            logger.error(f"❌ Audio file does not exist: {wav_file}")
            return
        
        # Set flag to disable microphone during playback
        self.is_playing_audio = True
        logger.info(f"🔇 Microphone disabled - starting audio playback: {wav_file}")
        
        try:
            with wave.open(wav_file, 'rb') as wf:
                sample_rate = wf.getframerate()
                channels = wf.getnchannels()
                data = wf.readframes(wf.getnframes())
                
                logger.info(f"🔊 Playing audio: {sample_rate}Hz/{channels}ch, {len(data)} bytes")
                
                # Calculate total duration
                total_samples = len(data) // (channels * 2)
                total_duration_seconds = total_samples / sample_rate
                
                logger.info(f"🔊 Audio duration: {total_duration_seconds:.2f}s, {total_samples} samples")
                
                # WebRTC best practice: Use 10ms chunks (standard for real-time audio)
                # This prevents buffer overflow and ensures smooth playback
                chunk_duration_ms = 10  # 10ms is WebRTC standard
                samples_per_chunk = int(sample_rate * chunk_duration_ms / 1000)
                bytes_per_chunk = samples_per_chunk * channels * 2
                
                logger.info(f"🔊 Streaming in {chunk_duration_ms}ms chunks: {samples_per_chunk} samples/chunk")
                
                # CRITICAL: Use AudioSource's sample rate for AudioFrame
                # This ensures LiveKit doesn't do internal resampling which can cause speed issues
                target_sample_rate = self.audio_source.sample_rate
                target_channels = CHANNELS  # AudioSource was created with CHANNELS
                
                if sample_rate != target_sample_rate or channels != target_channels:
                    logger.warning(f"⚠️ Resampling needed: {sample_rate}Hz/{channels}ch -> {target_sample_rate}Hz/{target_channels}ch")
                    # Use LiveKit's AudioResampler
                    resampler = rtc.AudioResampler(
                        input_rate=sample_rate,
                        output_rate=target_sample_rate,
                        num_channels=target_channels
                    )
                    # Create frame from original data
                    original_frame = rtc.AudioFrame(
                data=data,
                sample_rate=sample_rate,
                num_channels=channels,
                        samples_per_channel=total_samples
                    )
                    # Resample
                    resampled_frames = []
                    resampled_frames.extend(resampler.push(original_frame))
                    resampled_frames.extend(resampler.flush())
                    
                    if resampled_frames:
                        # Combine all resampled data
                        data = b''.join([f.data for f in resampled_frames])
                        sample_rate = target_sample_rate
                        channels = target_channels
                        total_samples = len(data) // (channels * 2)
                        samples_per_chunk = int(sample_rate * chunk_duration_ms / 1000)
                        bytes_per_chunk = samples_per_chunk * channels * 2
                        logger.info(f"🔄 Resampled: {len(data)} bytes, {total_samples} samples at {sample_rate}Hz")
                    else:
                        logger.error("❌ Resampling failed!")
                        return
                
                # Stream audio frames - LiveKit handles timing internally
                # No manual sleep needed - LiveKit's AudioSource manages buffer and timing
                # This prevents double timing which causes speed issues
                chunk_count = 0
                for i in range(0, len(data), bytes_per_chunk):
                    chunk = data[i:i+bytes_per_chunk]
                    
                    if len(chunk) < bytes_per_chunk:
                        # Last chunk - use actual size
                        if len(chunk) > 0:
                            actual_samples = len(chunk) // (channels * 2)
                            audio_frame = rtc.AudioFrame(
                                data=chunk,
                                sample_rate=target_sample_rate,  # Use AudioSource rate
                                num_channels=target_channels,   # Use AudioSource channels
                                samples_per_channel=actual_samples
                            )
                            await self.audio_source.capture_frame(audio_frame)
                            chunk_count += 1
                        break
                    else:
                        audio_frame = rtc.AudioFrame(
                            data=chunk,
                            sample_rate=target_sample_rate,  # Use AudioSource rate
                            num_channels=target_channels,     # Use AudioSource channels
                            samples_per_channel=samples_per_chunk
                        )
                        await self.audio_source.capture_frame(audio_frame)
                        chunk_count += 1
                
                logger.info(f"✅ Audio playback complete: {chunk_count} chunks sent")
        except Exception as e:
            logger.error(f"❌ Error playing audio: {e}", exc_info=True)
        finally:
            # Re-enable microphone after playback completes
            self.is_playing_audio = False
            logger.info(f"🎤 Microphone enabled - audio playback finished")

    async def _send_message_to_web(self, user_text: str, agent_text: str, audio_file: str):
        """Send message to web client via data channel with text and audio"""
        try:
            # Check if room and participant are available
            if not self.ctx.room or not self.ctx.room.local_participant:
                logger.error("❌ Room or local participant not available")
                return
            
            # Read audio file and encode as base64
            with open(audio_file, 'rb') as f:
                audio_data = f.read()
                audio_base64 = base64.b64encode(audio_data).decode('utf-8')
            
            logger.info(f"📦 Preparing message: {len(agent_text)} chars text, {len(audio_base64)} bytes audio (base64)")
            
            # Create message payload
            message = {
                "type": "agent_response",
                "user_text": user_text,
                "agent_text": agent_text,
                "audio_base64": audio_base64,
                "timestamp": datetime.now().isoformat()
            }
            
            # Encode message
            message_json = json.dumps(message)
            message_bytes = message_json.encode('utf-8')
            
            logger.info(f"📤 Sending message via data channel: {len(message_bytes)} bytes total")
            
            # Check message size - LiveKit has limits
            if len(message_bytes) > 1000000:  # 1MB limit
                logger.warning(f"⚠️ Message too large ({len(message_bytes)} bytes), truncating audio...")
                # Truncate audio if too large
                message["audio_base64"] = message["audio_base64"][:500000]  # Keep first 500KB
                message_json = json.dumps(message)
                message_bytes = message_json.encode('utf-8')
                logger.info(f"📦 Truncated message size: {len(message_bytes)} bytes")
            
            # Try HTTP endpoint first (more reliable than data channel)
            try:
                logger.info(f"📤 Sending message via HTTP to {WEB_API_URL} for room {self.ctx.room.name}")
                logger.info(f"📦 Message payload: type={message['type']}, user_text_len={len(user_text)}, agent_text_len={len(agent_text)}, audio_len={len(audio_base64)}")
                # Run blocking request in executor to avoid blocking event loop
                loop = asyncio.get_event_loop()
                
                def _make_http_request():
                    try:
                        logger.info(f"🌐 Making HTTP POST request to {WEB_API_URL}")
                        resp = requests.post(
                            WEB_API_URL,
                            json={
                                "roomName": self.ctx.room.name,
                                "message": message
                            },
                            timeout=30  # Increased timeout
                        )
                        logger.info(f"🌐 HTTP response status: {resp.status_code}")
                        return resp
                    except Exception as req_error:
                        logger.error(f"🌐 HTTP request error: {req_error}")
                        raise
                
                response = await loop.run_in_executor(None, _make_http_request)
                response.raise_for_status()
                logger.info(f"✅ Message sent successfully via HTTP: {len(agent_text)} chars, {len(audio_base64)} bytes audio")
                return  # Success, exit function
            except Exception as http_error:
                logger.error(f"❌ HTTP send failed: {http_error}", exc_info=True)
                import traceback
                logger.error(f"❌ HTTP error traceback: {traceback.format_exc()}")
                logger.warning(f"⚠️ Falling back to data channel...")
            
            # Fallback: Try data channel (original method)
            max_retries = 2
            for attempt in range(max_retries):
                try:
                    logger.info(f"🔄 Data channel attempt {attempt + 1}/{max_retries}...")
                    await asyncio.wait_for(
                        self.ctx.room.local_participant.publish_data(
                            payload=message_bytes,
                            reliable=True,
                            topic="agent-messages"
                        ),
                        timeout=10.0  # Shorter timeout for fallback
                    )
                    logger.info(f"✅ Message sent via data channel")
                    return
                except Exception as publish_error:
                    logger.error(f"❌ Data channel error (attempt {attempt + 1}/{max_retries}): {publish_error}")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(1)
            
            logger.error("❌ Failed to send message via both HTTP and data channel")
        except Exception as e:
            logger.error(f"❌ Error sending message to web: {e}", exc_info=True)

# ===== ENTRY POINT =====

async def entrypoint(ctx: JobContext):
    """Agent entry point"""
    # #region debug log
    debug_log("agent/main.py:341", "entrypoint called", {
        "room_name": ctx.room.name if ctx.room else None,
        "job_id": getattr(ctx, "job_id", None)
    }, "H3")
    # #endregion
    agent = VoiceAgent(ctx)
    await agent.start()

if __name__ == "__main__":
    # #region debug log
    debug_log("agent/main.py:346", "agent starting", {
        "has_entrypoint": entrypoint is not None
    }, "H3")
    # #endregion
    # Set agent_name for explicit dispatch
    cli.run_app(WorkerOptions(
        entrypoint_fnc=entrypoint,
        agent_name="voice-assistant"
    ))

