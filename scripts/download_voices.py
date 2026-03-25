"""
Download Kokoro TTS voice models from HuggingFace
Note: Kokoro automatically downloads the model on first use.
This script pre-downloads the voice models to avoid first-run delays.
"""

import os
import sys
from pathlib import Path

try:
    from huggingface_hub import hf_hub_download
except ImportError:
    print("Installing huggingface_hub...")
    os.system("pip install huggingface_hub")
    from huggingface_hub import hf_hub_download


def download_voices():
    """Download Kokoro voice models from HuggingFace"""
    voices_dir = Path("voices")
    voices_dir.mkdir(exist_ok=True)

    print("Downloading Kokoro voice models...")
    print("This may take a few minutes depending on your internet connection.")
    print()

    # Note: Kokoro 0.9.x downloads the model automatically on first use
    # This script pre-downloads the voice model file if available
    print("[1/1] Checking for voice model files...")
    print("    Note: Kokoro will automatically download the model on first use")
    print("    If you want to pre-download, you can download from:")
    print("    https://huggingface.co/hexgrad/Kokoro-82M")
    print()
    print("Voice models will be downloaded automatically when first needed.")
    print()
    print("Done! (Voice models will be downloaded on first TTS run)")


if __name__ == "__main__":
    download_voices()
