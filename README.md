# Deliberate AI

**Multi-Perspective Decision Analysis Through Simulated Expert Debate**

---

## What Is Deliberate AI?

**Deliberate AI is like having a virtual think tank to help you make important decisions.** Instead of asking a single AI for an answer, it creates a simulated debate among 12 expert personas with different backgrounds, perspectives, and areas of expertise.

Think of it as:
- **A decision support system** that shows you how different experts would analyze your situation
- **A stress-test for your thinking** against multiple expert perspectives
- **A way to identify blind spots** by seeing where experts disagree
- **A structured analysis tool** that reveals the reasoning behind recommendations

### What Can You Use It For?

**Real-World Examples:**

- **Investment Decisions:** "Should I invest $50,000 in this AI startup?"
  - Personas: Venture capitalist, industry analyst, risk manager, tech expert, consumer advocate
  
- **Major Purchases:** "Tesla or Rivian - which electric vehicle should I buy?"
  - Personas: Automotive engineer, environmental scientist, financial advisor, consumer advocate, fleet manager
  
- **Career Choices:** "Should I accept this job offer in a different city?"
  - Personas: Career counselor, family therapist, financial planner, relocation specialist, mentor
  
- **Policy Analysis:** "What will happen if this new law passes?"
  - Personas: Legal expert, economist, community advocate, business owner, policy analyst
  
- **Current Events:** "What's likely to happen with this international conflict?"
  - Personas: Diplomat, military analyst, humanitarian worker, economist, regional expert

**The result isn't just an answer—it's a comprehensive report showing you:**
- Where experts agree (consensus)
- Where they disagree (uncertainties)
- How opinions evolved through debate
- Which arguments were most persuasive
- What confidence level the analysis has
- Specific, actionable recommendations

---

## How It Works (Overview)

Deliberate AI creates 12 domain-specific expert personas relevant to your question. Each persona has:
- A specific role and organization
- Years of experience and detailed background
- A particular analytical approach

The personas then engage in structured debate over multiple rounds, reacting to each other's arguments, considering new evidence, and potentially shifting their positions. The system tracks:
- Who changed their mind and why
- Where consensus is forming
- Which experts were most influential
- Persistent disagreements that remain

The final report synthesizes this entire process into actionable insights.

**Want the full explanation?** See [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) for a detailed, beginner-friendly guide with examples.

---

## Key Features

### 🎯 Multi-Perspective Analysis
- 12 domain-specific expert personas
- Two debate modes: Simultaneous (fast) or Sequential (thorough)
- Tracks opinion evolution and influence patterns

### 🔍 Flexible LLM Support
- **Works with ANY OpenAI-compatible API endpoint**
- Use vLLM, OpenAI, Anthropic, Ollama, LM Studio, or any compatible server
- Simply configure the endpoint URL in settings

### 🌐 Optional Web Search
- **Supports ANY search API** that returns structured results
- Works with SearXNG, DuckDuckGo, Google Custom Search, or custom APIs
- Real-time fact-checking and current information
- Toggle on/off per simulation or globally

### 🔊 Text-to-Speech
- Natural-sounding audio reports using Kokoro TTS
- 15+ voice options (male, female, neutral)
- GPU acceleration (CUDA/MPS) with CPU fallback
- Auto-cleanup of audio files

### 💬 Interactive Persona Chat
- Continue conversations with individual experts
- Ask follow-up questions
- Enable web search for specific messages

### 📊 Comprehensive Reports
- Executive summary with key findings
- Predicted outcomes with reasoning
- Confidence levels and uncertainties
- Expert positions and evolution
- Consensus and disagreement areas
- Actionable recommendations
- "What if we voted?" comparison

---

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

3. **Configure your LLM endpoint**
   - Edit `settings.json` with your API endpoint
   - Or use the Settings dialog in the app
   - Works with vLLM, OpenAI, Ollama, LM Studio, etc.

4. **Launch the application**
   ```batch
   start.bat
   ```

---

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
- Access to an LLM endpoint (local or remote)

### Flexible Backend Support

**LLM Backends (any OpenAI-compatible API):**
- vLLM (local or remote)
- OpenAI API
- Anthropic Claude
- Ollama (local)
- LM Studio (local)
- Any server with OpenAI-compatible API

**Search Backends (any structured search API):**
- SearXNG (self-hosted or public instances)
- DuckDuckGo
- Google Custom Search API
- Brave Search API
- Custom search endpoints

**TTS Options:**
- CPU (works everywhere)
- NVIDIA GPU (CUDA acceleration)
- Apple Silicon (MPS acceleration)

---

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

**LLM Endpoint:**
- `vllm_endpoint_url`: URL of your LLM server (any OpenAI-compatible API)
  - Examples: `http://localhost:8000/v1`, `https://api.openai.com/v1`, `http://localhost:11434/v1`
- `model_name`: Name of the model to use
- `api_key`: API key (use "empty" if not required)

**Search Configuration:**
- `search_enabled`: Enable/disable web search by default
- `search_url`: URL of your search API endpoint
  - Examples: `http://localhost:8080/search` (SearXNG), `https://api.duckduckgo.com/`

### GUI Settings

You can also configure settings through the app:
1. Click **Settings** button
2. Update LLM endpoint, model name, API key
3. Configure web search settings (URL and enable/disable)
4. Click **Save**

---

## Usage

### Running a Simulation

1. Select input mode: **Question** or **Text**
2. Enter your question or paste text/document for analysis
3. Configure debate mode (Simultaneous/Sequential) in Settings
4. Optionally enable web search for current information
5. Click **Run Simulation**
6. Wait for analysis (typically 8-15 minutes)
7. Review the comprehensive report

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

---

## Understanding the Report

Deliberate AI generates comprehensive reports with these sections:

- **Executive Summary**: Complete overview of the debate and findings
- **Predicted Outcome**: Specific recommendations with detailed reasoning
- **Confidence Level**: How certain the analysis is (Low/Medium/High)
- **Expert Positions**: Where each persona stands and how they evolved
- **Consensus Areas**: Where experts agree (most reliable insights)
- **Persistent Disagreements**: Where experts still differ (key uncertainties)
- **Key Influencers**: Which experts were most persuasive
- **Wildcard Factors**: External events that could change outcomes
- **Recommended Actions**: Specific, actionable next steps
- **"If We Voted"**: Comparison with simple majority voting

**See [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md) for detailed explanations of each section.**

---

## Debate Modes

### Simultaneous Mode
- All personas respond at once
- Faster execution
- Good for quick analysis
- Supports up to 10 rounds

### Sequential Mode
- Personas respond one-by-one
- See previous responses before responding
- 3-5 rounds of debate
- More nuanced analysis
- Early convergence detection

---

## Troubleshooting

### LLM Connection Issues
- Verify your LLM server is running
- Check `settings.json` has correct endpoint URL
- Test connection: `curl http://localhost:8000/v1/models`
- Ensure your endpoint is OpenAI-compatible

### Web Search Not Working
- Verify your search API is accessible
- Check `search_url` in settings
- Test your search endpoint directly
- Ensure it returns structured JSON results

### TTS Not Working
- Ensure `voices/` folder contains `.onnx` files
- Check internet connection for initial voice download
- For GPU support, verify CUDA is installed
- TTS works on CPU if no GPU available

### GUI Freezes
- Ensure you're using the PyQt6 version
- Check that worker threads are properly connected
- Look for errors in `logs/error_log_*.log`

---

## Project Structure

```
Deliberate_AI_Github/
├── sos.py                    # Main entry point
├── pipeline.py               # Core simulation pipeline
├── ui.py                     # PyQt6 GUI
├── search.py                 # Search integration (any API)
├── error_tracker.py          # Error tracking
├── tts_client.py             # Kokoro TTS client
├── scripts/
│   ├── install.bat           # Windows installer
│   ├── start.bat             # Windows launcher
│   └── download_voices.py    # Voice model downloader
├── voices/                   # Downloaded voice models (gitignored)
├── output/                   # Generated audio (gitignored)
├── logs/                     # Error logs (gitignored)
├── reports/                  # Generated reports (gitignored)
├── saved_sessions/           # Chat sessions (gitignored)
├── requirements.txt          # Python dependencies
├── settings.json             # User configuration
├── settings.example.json     # Configuration template
├── HOW_IT_WORKS.md           # Detailed user guide
├── .gitignore               # Git ignore rules
└── LICENSE                  # Apache-2.0
```

---

## Documentation

- **README.md** (this file) - Quick start and overview
- **HOW_IT_WORKS.md** - Detailed beginner-friendly guide with examples
- **METHODOLOGY.md** - Technical methodology and research background
- **IMPLEMENTATION_SUMMARY.md** - Implementation details

---

## Development

### Adding New Personas

Edit the persona generation prompt in `pipeline.py` to add new domain experts.

### Customizing Debate Rounds

Modify `stage3_sequential_rounds()` in `pipeline.py` to change debate behavior.

### Adding Search Providers

The search module (`search.py`) is designed to work with any API that returns structured results. To add a new search provider:
1. Implement the search function to match the expected format
2. Update the search URL in settings
3. The system will use it automatically

### Adding Voices

Download additional Kokoro voices and place in `voices/` folder. Update voice list in `tts_client.py`.

---

## Why This Approach Works

Research in decision science shows that diverse groups consistently outperform even the smartest individual. Deliberate AI creates this diversity by design:

1. **Multiple Perspectives**: 12 different expert viewpoints beat a single opinion
2. **Structured Debate**: Identifies blind spots and builds nuanced positions
3. **Domain-Specific Experts**: Real expertise (not generic opinions) produces higher-quality analysis
4. **Trajectory Tracking**: Monitoring opinion changes reveals what arguments are most persuasive
5. **External Facts**: Web search integration prevents debate from becoming an echo chamber

**Learn more in [`HOW_IT_WORKS.md`](HOW_IT_WORKS.md).**

---

## Limitations

- **AI Simulations**: Personas are AI agents, not real humans
- **Input Quality**: "Garbage in, garbage out" - provide detailed context
- **Black Swans**: Can't predict unforeseeable high-impact events
- **Specialized Knowledge**: For highly technical topics, supplement with real expert consultation

**Best used as a decision support tool, not a crystal ball.**

---

## License

This project is licensed under the **Apache License 2.0** - see the [LICENSE](LICENSE) file for details.

Kokoro TTS is also Apache-2.0 licensed, making this combination ideal for both personal and commercial use.

---

## Credits

- **Concept**: Multi-agent debate system for decision analysis
- **GUI**: PyQt6 migration from CustomTkinter for improved performance
- **TTS**: Kokoro by hexgrad (https://github.com/hexgrad/kokoro)
- **Search**: Flexible architecture supporting multiple search APIs
- **Research**: Based on work from NeurIPS 2025 (Choi et al.) on debate systems

---

## Support

For issues and feature requests, use the GitHub Issues tracker.

---

## Version

Current version: 2.0 (PyQt6)

---

**Deliberate AI: Stress-test your thinking against a panel of expert perspectives.**
