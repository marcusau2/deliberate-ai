# Deliberate AI

**Multi-Agent Simulation for Decision Analysis**

Deliberate AI is an advanced multi-agent simulation system that brings together 12 domain-specific personas to debate and analyze complex questions. Using state-of-the-art LLMs and optional web search integration, it provides comprehensive, multi-perspective analysis for decision-making.

## Features

- **12 Domain-Specific Personas**: Expert AI agents with specialized knowledge
- **Two Debate Modes**: Simultaneous or Sequential debate rounds
- **Web Search Integration**: Optional real-time fact-checking with SearXNG
- **Text-to-Speech**: Natural-sounding audio reports using Kokoro TTS
- **Interactive Chat**: Continue conversations with individual personas
- **Comprehensive Reports**: Generate detailed analysis reports in multiple formats

## Quick Start

### Prerequisites

- Windows 10/11
- Python 3.9 or higher
- 4GB+ RAM (8GB recommended)
- Internet connection (for initial setup and optional web search)

### Installation

1. **Clone or download the repository**

2. **Run the installer**
   ```batch
   install.bat
   ```

   This will:
   - Create a virtual environment
   - Install all dependencies
   - Download Kokoro TTS voice models
   - Set up the application

3. **Configure settings**
   - Edit `settings.json` with your vLLM endpoint and model name
   - Or use the Settings dialog in the app (Settings button)

4. **Launch the application**
   ```batch
   start.bat
   ```

## System Requirements

### Minimum
- Windows 10/11
- 4GB RAM
- Python 3.9+
- Internet connection (for initial setup)

### Recommended
- Windows 10/11
- 8GB+ RAM
- NVIDIA GPU (optional, for faster TTS)
- vLLM server running locally or remotely

### Optional Components
- **vLLM Server**: For running LLM inference (local or remote)
- **SearXNG**: For web search integration (local instance at `http://localhost:8080`)
- **CUDA-capable GPU**: For accelerated TTS generation

## Configuration

### settings.json

The main configuration file. Key settings:

```json
{
  "vllm_endpoint_url": "http://localhost:8000/v1",
  "model_name": "your-model-name",
  "api_key": "your-api-key",
  "search_enabled": false,
  "search_url": "http://localhost:8080/search"
}
```

- **vllm_endpoint_url**: URL of your vLLM server
- **model_name**: Name or path of the model to use
- **api_key**: API key for vLLM (use "empty" if not required)
- **search_enabled**: Enable/disable web search by default
- **search_url**: SearXNG endpoint URL

### GUI Settings

You can also configure settings through the app:
1. Click **Settings** button
2. Update vLLM endpoint, model name, API key
3. Configure web search settings
4. Click **Save**

## Usage

### Running a Simulation

1. Select input mode: **Question** or **Text**
2. Enter your question or paste text
3. Configure debate mode (Simultaneous/Sequential) in Settings
4. Optionally enable web search
5. Click **Run Simulation**

### Chat with Personas

After a simulation completes:
1. Go to the **Persona Chat** tab
2. Select a persona
3. Send messages and receive responses
4. Optionally enable web search for individual messages

### Generate Audio Reports

1. After simulation, go to **Report** tab
2. Select voice from dropdown
3. Click **Play** to generate and listen to the report
4. Audio files are saved to `output/tts_audio/`

## Architecture

### Core Components

- **Pipeline**: 6-stage simulation pipeline
  1. Situation extraction
  2. Persona generation
  3. Debate rounds
  4. Round compression
  5. Report generation
  6. Final report formatting

- **Personas**: 12 domain experts
  - Political Analyst
  - Economic Advisor
  - Military Strategist
  - Social Scientist
  - Environmental Expert
  - Technology Analyst
  - Legal Counsel
  - Healthcare Specialist
  - Education Expert
  - Business Leader
  - Cultural Critic
  - Ethical Philosopher

### Technologies

- **GUI**: PyQt6
- **LLM**: vLLM with any compatible model
- **TTS**: Kokoro PyTorch (auto-detects GPU/CPU)
- **Search**: SearXNG integration
- **Audio**: scipy, sounddevice

## Debates Modes

### Simultaneous Mode
- All personas respond at once
- Faster execution
- Good for quick analysis

### Sequential Mode
- Personas respond one-by-one
- 3-5 rounds of debate
- Early convergence detection
- More thorough analysis

## TTS (Text-to-Speech)

### Voice Options
- **af_bella** (default) - American female
- **af_heart**, **af_nicole**, **af_alloy** - American female
- **am_michael**, **am_fenrir**, **am_puck** - American male
- And 8 more voices

### Performance
- **CPU**: ~6× real-time generation
- **GPU (CUDA)**: Significantly faster
- **First load**: 3-5 seconds (model loading)
- **Subsequent**: <1 second for short text

### Audio Files
- All generated audio is saved to `output/tts_audio/`
- Files are automatically cleaned up (older than 24 hours)
- Format: WAV (16-bit, 24kHz)

## Troubleshooting

### TTS Not Working
- Ensure `voices/` folder contains `.onnx` files
- Check internet connection for initial voice download
- For GPU support, verify CUDA is installed

### vLLM Connection Issues
- Verify vLLM server is running
- Check `settings.json` has correct endpoint URL
- Test connection: `curl http://localhost:8000/v1/models`

### Web Search Not Working
- Install and run SearXNG locally
- Or configure a public SearXNG instance
- Check `search_url` in settings

### GUI Freezes
- Ensure you're using the PyQt6 version (not CustomTkinter)
- Check that worker threads are properly connected
- Look for errors in `logs/error_log_*.log`

## Project Structure

```
Deliberate_AI_Github/
├── src/
│   ├── sos.py              # Main entry point
│   ├── pipeline.py         # Core simulation pipeline
│   ├── ui.py               # PyQt6 GUI
│   ├── search.py           # SearXNG integration
│   ├── error_tracker.py    # Error tracking
│   └── tts_client.py       # Kokoro TTS client
├── scripts/
│   ├── install.bat         # Windows installer
│   ├── start.bat           # Windows launcher
│   └── download_voices.py  # Voice model downloader
├── voices/                 # Downloaded voice models (gitignored)
├── output/                 # Generated audio (gitignored)
├── logs/                   # Error logs (gitignored)
├── reports/                # Generated reports (gitignored)
├── saved_sessions/         # Chat sessions (gitignored)
├── requirements.txt        # Python dependencies
├── settings.json           # User configuration
├── .gitignore             # Git ignore rules
└── LICENSE                # Apache-2.0
```

## Development

### Adding New Personas

Edit the persona generation prompt in `pipeline.py` to add new domain experts.

### Customizing Debate Rounds

Modify `stage3_sequential_rounds()` in `pipeline.py` to change debate behavior.

### Adding Voices

Download additional Kokoro voices and place in `voices/` folder. Update voice list in `tts_client.py`.

## License

This project is licensed under the **Apache License 2.0** - see the [LICENSE](LICENSE) file for details.

Kokoro TTS is also Apache-2.0 licensed, making this combination ideal for both personal and commercial use.

## Credits

- **Original Concept**: Multi-agent debate system for decision analysis
- **GUI Migration**: From CustomTkinter to PyQt6 for improved performance
- **TTS Integration**: Kokoro by hexgrad (https://github.com/hexgrad/kokoro)
- **Search**: SearXNG metasearch engine

## Support

For issues and feature requests, please use the GitHub Issues tracker.

## Version

Current version: 2.0 (PyQt6)

---

**Ready to make better decisions through collective intelligence.**
