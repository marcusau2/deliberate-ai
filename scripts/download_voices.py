"""
Download Kokoro TTS voice models from HuggingFace
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

    # Download main model
    print("[1/2] Downloading kokoro-v1.0.onnx...")
    try:
        hf_hub_download(
            repo_id="hexgrad/Kokoro-82M",
            filename="kokoro-v1.0.onnx",
            local_dir=voices_dir,
            local_dir_use_symlinks=False,
        )
        print("    ✓ Downloaded kokoro-v1.0.onnx")
    except Exception as e:
        print(f"    ✗ Failed to download kokoro-v1.0.onnx: {e}")
        print("    Will be downloaded on first run")

    print()

    # Download voices file
    print("[2/2] Downloading voices-v1.0.bin...")
    try:
        hf_hub_download(
            repo_id="hexgrad/Kokoro-82M",
            filename="voices-v1.0.bin",
            local_dir=voices_dir,
            local_dir_use_symlinks=False,
        )
        print("    ✓ Downloaded voices-v1.0.bin")
    except Exception as e:
        print(f"    ✗ Failed to download voices-v1.0.bin: {e}")
        print("    Will be downloaded on first run")

    print()
    print("Voice models download complete!")
    print("Files saved to: voices/")
    print()
    print("Note: If download failed, voices will be automatically downloaded")
    print("      on first TTS run when needed.")


if __name__ == "__main__":
    download_voices()
