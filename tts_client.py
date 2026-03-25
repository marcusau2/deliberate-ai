"""
Kokoro PyTorch TTS Client for Deliberate AI
Fast, natural-sounding text-to-speech using Kokoro with CUDA GPU acceleration
"""

import sys
import os
import threading
import numpy as np
import sounddevice as sd
import torch
from typing import Optional, Callable
from pathlib import Path
from loguru import logger

# Output directory for TTS WAV files
TTS_OUTPUT_DIR = Path("output/tts_audio")
TTS_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


class TTSClient:
    """Client for Kokoro PyTorch TTS with GPU support"""

    def __init__(self):
        self.is_playing = False
        self._lock = threading.Lock()
        self._model = None
        self._voices = None
        self._sample_rate = 24000
        self._device = None
        self._current_audio_path = None
        self._load_model()

    def _load_model(self):
        """Load Kokoro PyTorch TTS model with GPU support"""
        try:
            from kokoro import KPipeline

            print("[TTS Client] Loading Kokoro PyTorch model...", file=sys.stderr)

            # Detect device (GPU or CPU)
            if torch.cuda.is_available():
                self._device = "cuda"
                print(
                    f"[TTS Client] CUDA available: {torch.cuda.get_device_name(0)}",
                    file=sys.stderr,
                )
                print(
                    f"[TTS Client] CUDA memory allocated: {torch.cuda.memory_allocated() / 1024**2:.1f} MB",
                    file=sys.stderr,
                )
            elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
                self._device = "mps"
                print(f"[TTS Client] Using Apple MPS", file=sys.stderr)
            else:
                self._device = "cpu"
                print(f"[TTS Client] Using CPU (no GPU available)", file=sys.stderr)

            # Initialize Kokoro pipeline with GPU
            # Using en-us language code for American English
            self._pipeline = KPipeline(lang_code="en-us", device=self._device)

            # Get available voices from the pipeline
            # Kokoro voices follow the pattern: af_* (American female), am_* (American male), etc.
            # Based on https://huggingface.co/hexgrad/Kokoro-82M/blob/main/VOICES.md
            self._voices = [
                # American English Female (best quality first)
                "af_bella",
                "af_heart",
                "af_nicole",
                "af_alloy",
                "af_aoede",
                "af_kore",
                "af_sarah",
                "af_jessica",
                "af_nova",
                "af_river",
                "af_sky",
                # American English Male
                "am_michael",
                "am_fenrir",
                "am_puck",
                "am_adam",
                "am_eric",
                "am_echo",
                "am_liam",
                "am_onyx",
                "am_santa",
                # British English
                "bf_emma",
                "bf_isabella",
                "bf_alice",
                "bf_lily",
                "bm_daniel",
                "bm_fable",
                "bm_george",
                "bm_lewis",
            ]
            self._default_voice = "af_bella"  # Highest quality American female voice

            print(
                f"[TTS Client] Kokoro loaded on {self._device.upper()}", file=sys.stderr
            )
            print(f"[TTS Client] Available voices: {self._voices[:5]}", file=sys.stderr)

        except Exception as e:
            print(f"[TTS Client] Error loading Kokoro: {e}", file=sys.stderr)
            import traceback

            traceback.print_exc(file=sys.stderr)
            raise

    @property
    def available_voices(self):
        """Get available voices"""
        return self._voices[:5] if self._voices else ["Default"]

    @property
    def current_voice(self):
        """Get current voice"""
        return getattr(self, "_default_voice", "af_bella")

    @current_voice.setter
    def current_voice(self, voice):
        """Set current voice"""
        if self._voices and voice in self._voices:
            self._default_voice = voice

    def estimate_duration(self, text: str) -> float:
        """Estimate audio duration in seconds"""
        word_count = len(text.split())
        return word_count / 4.5

    def generate_and_play(
        self,
        text: str,
        voice: str = None,
        save_to_file: bool = True,
        progress_callback: Optional[Callable] = None,
        complete_callback: Optional[Callable] = None,
    ):
        """Generate and play audio using Kokoro PyTorch"""
        if voice is None:
            voice = getattr(self, "_default_voice", "af_bella")

        def _playback_thread():
            try:
                if progress_callback:
                    progress_callback("Generating audio...")

                # Generate audio using Kokoro PyTorch
                audio = self._generate_audio(text, voice)

                # Save to file if requested
                if save_to_file:
                    self._current_audio_path = self._save_audio_to_wav(audio, text)
                    if progress_callback:
                        progress_callback(f"Audio saved to {self._current_audio_path}")

                if progress_callback:
                    progress_callback("Playing audio...")

                # Play audio
                with self._lock:
                    self.is_playing = True

                sd.play(audio, self._sample_rate)
                sd.wait()

                with self._lock:
                    self.is_playing = False

                if complete_callback:
                    complete_callback()

            except Exception as e:
                print(f"[TTS Client] Error: {e}", file=sys.stderr)
                import traceback

                traceback.print_exc(file=sys.stderr)
                if complete_callback:
                    complete_callback(error=str(e))

        # Start playback in background thread
        thread = threading.Thread(target=_playback_thread)
        thread.daemon = True
        thread.start()

    def _generate_audio(self, text: str, voice: str):
        """Generate audio from text using Kokoro PyTorch"""
        # Generate audio using the pipeline
        # Kokoro pipeline yields (text, phonemes, audio) tuples where audio is a torch tensor
        audio_chunks = []

        try:
            for result in self._pipeline(text, voice=voice, speed=1.0):
                # Kokoro returns (text, phonemes, audio) where audio is the last element
                # The audio is a torch tensor that needs to be converted to numpy
                if len(result) >= 3:
                    audio_tensor = result[-1]  # Last element is the audio tensor

                    # Convert torch tensor to numpy array
                    if hasattr(audio_tensor, "detach"):
                        # It's a PyTorch tensor
                        audio_array = audio_tensor.detach().cpu().numpy()
                    else:
                        # Already numpy or convertable
                        audio_array = np.array(audio_tensor)

                    # Ensure it's a 1D array
                    audio_array = audio_array.flatten()

                    if audio_array.size > 0:
                        audio_chunks.append(audio_array)

            if not audio_chunks:
                raise ValueError("No audio generated")

            # Concatenate all audio chunks
            if len(audio_chunks) == 1:
                audio = audio_chunks[0]
            else:
                audio = np.concatenate(audio_chunks)

            return audio

        except Exception as e:
            print(f"[TTS Client] Audio generation error: {e}", file=sys.stderr)
            raise

    def _save_audio_to_wav(self, audio: np.ndarray, text: str) -> Path:
        """Save audio to WAV file in output directory"""
        import hashlib
        from datetime import datetime

        # Generate unique filename based on text hash and timestamp
        text_hash = hashlib.md5(text.encode()).hexdigest()[:8]
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"tts_{timestamp}_{text_hash}.wav"
        filepath = TTS_OUTPUT_DIR / filename

        # Save using scipy
        try:
            from scipy.io import wavfile

            # Normalize to 16-bit range
            audio_normalized = audio / np.max(np.abs(audio))
            audio_16bit = (audio_normalized * 32767).astype(np.int16)

            wavfile.write(filepath, self._sample_rate, audio_16bit)
            return filepath
        except ImportError:
            print(
                "[TTS Client] scipy not available for WAV saving, skipping file save",
                file=sys.stderr,
            )
            return None

    @staticmethod
    def cleanup_tts_folder():
        """Clean up old TTS audio files (keep last 24 hours)"""
        from datetime import datetime, timedelta

        if not TTS_OUTPUT_DIR.exists():
            return

        cutoff_time = datetime.now() - timedelta(hours=24)
        deleted_count = 0

        for file_path in TTS_OUTPUT_DIR.glob("*.wav"):
            try:
                file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if file_mtime < cutoff_time:
                    file_path.unlink()
                    deleted_count += 1
            except Exception as e:
                print(f"[TTS Client] Error deleting {file_path}: {e}", file=sys.stderr)

        if deleted_count > 0:
            print(
                f"[TTS Client] Cleaned up {deleted_count} old TTS files",
                file=sys.stderr,
            )

    def stop(self):
        """Stop audio playback"""
        try:
            sd.stop()
            with self._lock:
                self.is_playing = False
        except Exception as e:
            print(f"[TTS Client] Error stopping: {e}", file=sys.stderr)


# Global singleton instance (lazy initialization)
tts_client = None


def get_tts_client():
    """Get TTS client instance, initializing on first call"""
    global tts_client
    if tts_client is None:
        tts_client = TTSClient()
    return tts_client
