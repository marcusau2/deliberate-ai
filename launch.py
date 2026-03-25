"""
Launcher for Deliberate AI with comprehensive error handling
This script catches all errors and displays them in a user-friendly way
"""

import sys
import traceback
from pathlib import Path


def check_python_version():
    """Check if Python version is compatible"""
    version = sys.version_info
    if version.major != 3 or version.minor < 10 or version.minor > 12:
        print(f"[ERROR] Python 3.10, 3.11, or 3.12 required.")
        print(
            f"        Current version: {version.major}.{version.minor}.{version.micro}"
        )
        print("\nPlease install Python 3.10-3.12 from https://www.python.org/")
        return False
    print(f"[OK] Python {version.major}.{version.minor}.{version.micro}")
    return True


def check_visual_cpp():
    """Check for Visual C++ Redistributable"""
    try:
        import winreg

        try:
            key = winreg.OpenKey(
                winreg.HKEY_LOCAL_MACHINE,
                r"SOFTWARE\Microsoft\VisualStudio\14.0\VC\Runtimes\x64",
            )
            version, _ = winreg.QueryValueEx(key, "Version")
            print(f"[OK] Visual C++ Redistributable found: {version}")
            winreg.CloseKey(key)
            return True
        except FileNotFoundError:
            print("[WARNING] Visual C++ Redistributable not found!")
            print(
                "          Download from: https://aka.ms/vs/17/release/vc_redist.x64.exe"
            )
            print("          The app may fail to start without it.")
            return True  # Continue anyway, might still work
    except ImportError:
        print("[INFO] Could not check Visual C++ (non-Windows?)")
        return True


def check_dependencies():
    """Check if all required packages are installed"""
    # Import torch FIRST (before PyQt6) to avoid DLL conflicts
    try:
        import torch

        print(f"[OK] torch (v{torch.__version__})")
    except ImportError as e:
        print(f"[ERROR] torch: {e}")
        return False
    except OSError as e:
        print(f"[DLL ERROR] torch: {e}")
        print("\nThis is typically caused by:")
        print("  1. Missing Visual C++ Redistributable")
        print("  2. PyQt6 loaded before torch")
        print("\nSolutions:")
        print(
            "  1. Install Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe"
        )
        print("  2. Restart your computer after installing VC++")
        return False

    # Import numpy
    try:
        import numpy

        print("[OK] numpy")
    except ImportError as e:
        print(f"[ERROR] numpy: {e}")
        return False

    # Check other packages
    other_packages = [
        ("PyQt6", "PyQt6"),
        ("kokoro", "kokoro"),
        ("openai", "openai"),
        ("yaml", "pyyaml"),  # Package name is pyyaml, import name is yaml
        ("PyPDF2", "PyPDF2"),  # Package name is PyPDF2, import name is PyPDF2
        ("requests", "requests"),
        ("scipy", "scipy"),
        ("sounddevice", "sounddevice"),
        ("soundfile", "soundfile"),
        ("loguru", "loguru"),
    ]

    for import_name, display_name in other_packages:
        try:
            __import__(import_name)
            print(f"[OK] {display_name}")
        except ImportError as e:
            print(f"[ERROR] {display_name}: {e}")
            return False

    return True


def launch_app():
    """Try to launch the main application"""
    print("\n" + "=" * 60)
    print("Attempting to launch Deliberate AI GUI...")
    print("=" * 60 + "\n")

    try:
        # Import main module
        from ui import main

        print("[OK] All imports successful!")
        print("\nLaunching GUI...")
        print("-" * 60)

        # Launch the app
        main()

    except OSError as e:
        print(f"\n[DLL ERROR] {e}")
        print("\nThis is typically caused by:")
        print("  1. Missing Visual C++ Redistributable")
        print("  2. PyTorch/PyQt6 DLL conflict")
        print("\nSolutions:")
        print(
            "  1. Install Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe"
        )
        print("  2. Restart your computer after installing VC++")
        print("  3. Make sure you're using Python 3.10-3.12")
        traceback.print_exc()

    except ImportError as e:
        print(f"\n[IMPORT ERROR] {e}")
        print("\nTry installing missing packages:")
        print("  pip install -r requirements.txt")
        traceback.print_exc()

    except Exception as e:
        print(f"\n[UNEXPECTED ERROR] {e}")
        print("\nFull traceback:")
        traceback.print_exc()

    finally:
        print("\n" + "=" * 60)
        print("Press Enter to exit...")
        input()


def main():
    """Main entry point"""
    print("=" * 60)
    print("  Deliberate AI - Launcher")
    print("=" * 60)
    print()

    # Check Python version
    if not check_python_version():
        sys.exit(1)

    # Check Visual C++
    check_visual_cpp()

    # Check dependencies
    if not check_dependencies():
        sys.exit(1)

    # Try to launch
    launch_app()


if __name__ == "__main__":
    main()
