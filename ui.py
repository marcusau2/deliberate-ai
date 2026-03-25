"""
UI for Deliberate AI using PyQt6
Migrated from CustomTkinter to PyQt6 for better threading and responsiveness
"""

import sys
import json
import yaml
import os
import re
import traceback
from datetime import datetime
from typing import Optional, Callable

from PyQt6.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QPushButton,
    QLabel,
    QTextEdit,
    QTextBrowser,
    QLineEdit,
    QComboBox,
    QCheckBox,
    QSplitter,
    QTabWidget,
    QScrollArea,
    QFrame,
    QStatusBar,
    QMessageBox,
    QFileDialog,
    QGroupBox,
    QDialog,
    QSlider,
)
from PyQt6.QtCore import (
    Qt,
    QRunnable,
    QThreadPool,
    pyqtSignal,
    QObject,
    QTimer,
    pyqtSlot,
)
from PyQt6.QtGui import QFont

from pipeline import Pipeline
from tts_client import get_tts_client, TTSClient
from error_tracker import error_tracker, log_pipeline_error, log_ui_error
from search import search_searxng, check_searxng_reachable

# TTS client will be initialized lazily when first needed
tts_client = None

# Set application style
QApplication.setStyle("Fusion")


class WorkerSignals(QObject):
    """Signals for worker thread communication"""

    finished = pyqtSignal()
    error = pyqtSignal(tuple)
    result = pyqtSignal(object)
    progress = pyqtSignal(str)
    log_message = pyqtSignal(str)
    persona_added = pyqtSignal(dict)
    round_complete = pyqtSignal(dict)


class TTSGenerationWorker(QRunnable):
    """Worker for generating TTS audio in background thread"""

    def __init__(self, text: str, voice_index: int = 0, save_to_file: bool = True):
        super().__init__()
        self.signals = WorkerSignals()
        self.text = text
        self.voice_index = voice_index
        self.save_to_file = save_to_file

    @pyqtSlot()
    def run(self):
        """Generate and play audio in background thread"""
        try:
            self.signals.progress.emit("Initializing TTS...")

            # Get TTS client instance
            client = get_tts_client()
            voice = (
                client.available_voices[self.voice_index]
                if self.voice_index < len(client.available_voices)
                else "alba"
            )

            # Generate and play (this blocks until playback is complete)
            # Save to file if requested
            client.generate_and_play(
                self.text,
                voice=voice,
                save_to_file=self.save_to_file,
                progress_callback=lambda msg: self.signals.progress.emit(msg),
                complete_callback=lambda error=None: self.signals.finished.emit(),
            )

        except Exception as e:
            self.signals.error.emit((str(e), "TTS Generation Failed"))


class PersonaResponseWorker(QRunnable):
    """Worker for generating persona responses in background thread"""

    def __init__(
        self,
        persona,
        user_message,
        pipeline,
        current_question,
        predicted_outcome,
        chat_history=None,
        search_enabled=False,
    ):
        super().__init__()
        self.signals = WorkerSignals()
        self.persona = persona
        self.user_message = user_message
        self.pipeline = pipeline
        self.current_question = current_question
        self.predicted_outcome = predicted_outcome
        self.chat_history = chat_history or []
        self.search_enabled = search_enabled

    @pyqtSlot()
    def run(self):
        """Generate response in background thread"""
        try:
            search_context = None

            # Smart web search if enabled
            if self.search_enabled:
                # Check if search is needed using hybrid approach
                needs_search, queries = self._analyze_for_search_needed(
                    self.user_message
                )

                if needs_search and queries:
                    # Show searching status
                    self.signals.progress.emit(f"Searching: {queries[0]}...")

                    # Perform web search
                    search_context = self._perform_web_search(queries)

            # Build prompt (with or without search context)
            prompt = self._build_prompt(search_context)

            # Call LLM with conversation history if available
            messages = [{"role": "user", "content": prompt}]

            # Add conversation history if it exists
            if self.chat_history:
                # Insert history before the current message
                for msg in self.chat_history[-5:]:  # Last 5 messages for context
                    role = (
                        "assistant"
                        if msg["role"] == self.persona.get("name")
                        else "user"
                    )
                    messages.insert(0, {"role": role, "content": msg["text"]})

            # Call LLM with raw response for conversational chat
            # Use minimal stop sequences to avoid cutting off detailed responses
            stop_sequences = ["\n\n\n", "\n---", "END OF RESPONSE"]

            response = self.pipeline.call_llm(
                messages,
                thinking=False,
                temperature=0.7,
                max_tokens=1200,  # Increased to allow more detailed responses
                raw_response=True,
                stop_sequences=stop_sequences,
            )

            # Response should be a string now
            result = (
                response.strip() if isinstance(response, str) else str(response).strip()
            )

            # Emit result
            self.signals.result.emit(result)
            self.signals.finished.emit()

        except Exception as e:
            error_msg = str(e).lower()
            if "json" in error_msg and "parse" in error_msg:
                error = "Error: The AI response format was invalid. Please try again."
            elif "timeout" in error_msg:
                error = "Error: The request timed out. Please try again."
            else:
                error = f"Error generating response: {str(e)[:100]}"
            self.signals.error.emit((type(e), Exception(error), traceback.format_exc()))

    def _build_prompt(self, search_context: Optional[str] = None):
        """Build the prompt for the persona - detailed, direct answers with full context"""
        persona = self.persona
        predicted_outcome = self.predicted_outcome
        current_question = self.current_question

        # Build complete conversation history context
        conversation_context = ""
        if self.chat_history:
            conversation_context = "COMPLETE CONVERSATION HISTORY:\n"
            for i, msg in enumerate(self.chat_history, 1):
                conversation_context += f"{i}. {msg['role']}: {msg['text']}\n"
            conversation_context += "\n"

        prompt = f"""You are {persona.get("name", "")}, a {persona.get("role_title", "")} at {persona.get("organization", "")}.

YOUR EXPERTISE:
- Approach: {persona.get("approach", "")}
- Background: {persona.get("background", "")}
- Your assessment from the analysis: {persona.get("initial_position", "")}

ORIGINAL QUESTION BEING ANALYZED:
{current_question if current_question else "Unknown"}

FINAL CONCLUSION FROM ANALYSIS:
{predicted_outcome}

{conversation_context}
CURRENT MESSAGE FROM USER:
{self.user_message}

CRITICAL RESPONSE REQUIREMENTS:

1. **ANSWER THE EXACT QUESTION ASKED** - Don't deflect, don't change the subject, don't talk around it. If they ask about X, answer about X. Give them what they're asking for.

2. **BE EXTREMELY DETAILED** - Don't give short, vague answers. Provide thorough, comprehensive explanations with specific examples, reasoning, and insights. Minimum 300-500 words.

3. **NO AVOIDANCE** - If the user asks for clarification on a specific point, give it. Don't pivot to a different topic. Don't say "that's complex" without actually explaining the complexity.

4. **INCORPORATE CONVERSATION HISTORY** - Reference what the user has already told you. Build on their insights. Show you're listening to the full conversation, not just the last message.

5. **BE SPECIFIC** - Use concrete examples, specific mechanisms, detailed reasoning. Don't be vague or academic.

6. **NO REPETITION** - Don't repeat the same points from earlier in the conversation. Add new insights, build on what's been discussed.

7. **BE DIRECT** - No hedging, no "it depends" without explanation, no vague generalizations. Give a substantive answer.

8. **VALIDATE USER INSIGHTS** - If the user makes an astute observation, acknowledge it and explain why it's clinically significant.
"""

        # Add search context if available
        if search_context:
            prompt += f"""
CURRENT INFORMATION (from web search):
{search_context}

INSTRUCTIONS: Use this current information to provide accurate, up-to-date responses. Integrate this information naturally into your response without mentioning that you searched for it. Just provide the information seamlessly.

"""

        prompt += f"""
Respond as {persona.get("name", "")} would - give a DIRECT, COMPREHENSIVE, detailed answer that actually addresses what the user is asking. No deflection, no vagueness, no evasion. Answer the question fully with your full expertise."""

        return prompt

    def _analyze_for_search_needed(self, user_message: str) -> tuple:
        """
        Hybrid approach: heuristic first, then LLM if needed.
        Returns (needs_search: bool, queries: list)
        """
        # Step 1: Heuristic detection (fast)
        current_indicators = [
            "recently",
            "currently",
            "now",
            "latest",
            "new",
            "just",
            "what's happening",
            "what happened",
            "update",
            "trends",
            "2024",
            "2025",
            "2026",
            "this year",
            "recent developments",
            "look up",
            "search for",
            "check current",
            "what's the latest",
        ]

        message_lower = user_message.lower()
        has_clear_indicator = any(ind in message_lower for ind in current_indicators)

        # If clear indicator, proceed to search
        if has_clear_indicator:
            queries = self._extract_search_topics(user_message)
            return True, queries

        # Step 2: For unclear cases, use LLM to decide
        # Check for ambiguous cases that might need search
        ambiguous_patterns = [
            "is it true",
            "verify",
            "confirm",
            "facts about",
            "statistics",
        ]
        has_ambiguous = any(pat in message_lower for pat in ambiguous_patterns)

        if has_ambiguous:
            # Use LLM for final decision
            try:
                analysis_prompt = f"""Analyze if web search would help answer this: "{user_message[:150]}"
Respond with JSON: {{"needs_search": true/false, "queries": ["query1", "query2"]}}"""

                response = self.pipeline.call_llm(
                    [{"role": "user", "content": analysis_prompt}],
                    max_tokens=100,
                    temperature=0.3,
                    raw_response=True,
                )

                import json

                analysis = json.loads(response)
                if analysis.get("needs_search"):
                    return True, analysis.get("queries", [])[:3]
            except:
                pass

        return False, []

    def _extract_search_topics(self, message: str) -> list:
        """Extract key topics from message for search queries"""
        # Simple keyword extraction
        stop_words = {
            "what",
            "is",
            "the",
            "a",
            "an",
            "in",
            "on",
            "at",
            "to",
            "for",
            "about",
            "with",
        }
        words = message.lower().replace("?", "").replace(".", "").split()
        keywords = [w for w in words if w not in stop_words and len(w) > 3]

        # Create 2-3 search queries
        queries = []
        if len(keywords) >= 2:
            queries.append(" ".join(keywords[:3]))
            if len(keywords) > 3:
                queries.append(" ".join(keywords[1:5]))
        elif keywords:
            queries.append(
                keywords[0] + " " + keywords[1] if len(keywords) > 1 else keywords[0]
            )

        return queries[:3]

    def _perform_web_search(self, queries: list) -> str:
        """Execute web searches and format results"""
        from search import search_searxng

        all_results = []

        # Search each query
        for query in queries[:5]:  # Max 5 queries
            results = search_searxng(query, num_results=5)
            all_results.extend(results[:2])  # Take top 2 from each query

        if not all_results:
            return "No search results found."

        # Format results (max 7 total)
        formatted = "CURRENT INFORMATION FROM WEB SEARCH:\n\n"
        for i, result in enumerate(all_results[:7], 1):
            title = result.get("title", "No title")
            snippet = result.get("snippet", "No content")
            formatted += f"{i}. {title}\n   {snippet[:250]}...\n\n"

        return formatted

    def _build_prompt_with_search(self, search_context: str) -> str:
        """Build prompt with search context included - deprecated, use _build_prompt instead"""
        return self._build_prompt(search_context)


class SimulationWorker(QRunnable):
    """Worker for running the complete simulation"""

    def __init__(
        self,
        situation,
        pipeline,
        settings,
        search_reachable,
        debate_mode="simultaneous",
        num_rounds=5,
    ):
        super().__init__()
        self.signals = WorkerSignals()
        self.situation = situation
        self.pipeline = pipeline
        self.settings = settings
        self.search_reachable = search_reachable
        self.debate_mode = debate_mode
        self.num_rounds = num_rounds

    def _format_search_results(self, results: list) -> str:
        """Format search results into a readable context string."""
        if not results:
            return "No search results found."

        formatted = "SEARCH RESULTS:\n\n"
        for i, result in enumerate(results, 1):
            title = result.get("title", "No title")
            snippet = result.get("snippet", "No content")
            formatted += f"{i}. {title}\n   {snippet[:300]}...\n\n"

        return formatted

    @pyqtSlot()
    def run(self):
        """Run simulation in background thread"""
        try:
            self.signals.progress.emit("Starting simulation...")

            # The situation is already a dict with "question" key
            original_input = self.situation.get("question", "")
            self.signals.log_message.emit(f"Input: {original_input[:100]}...")

            # Check web search availability
            search_available = self.search_reachable
            search_context = None
            if search_available:
                try:
                    self.signals.progress.emit("Checking web search availability...")
                    search_available = check_searxng_reachable()
                    if search_available:
                        self.signals.log_message.emit("Web search is available")
                    else:
                        self.signals.log_message.emit("Web search unavailable")
                except Exception as e:
                    self.signals.log_message.emit(
                        f"Web search check failed: {str(e)[:100]}"
                    )
                    search_available = False

            # Initialize round_history
            round_history = []

            # Stage 1: Extract situation with web search context if available
            self.signals.progress.emit("Stage 1: Situation Extraction")
            if search_available:
                self.signals.progress.emit("Searching for current information...")
                try:
                    # Generate search queries from the input
                    search_queries = [
                        original_input[:100],
                        f"current status {original_input[:80]}",
                        f"latest news {original_input[:70]}",
                    ]

                    all_results = []
                    for query in search_queries:
                        results = search_searxng(query, num_results=5)
                        all_results.extend(results)

                    # Format search results
                    search_context = self._format_search_results(all_results)
                    self.signals.log_message.emit(
                        f"Web search found {len(all_results)} relevant results"
                    )
                except Exception as e:
                    self.signals.log_message.emit(f"Web search failed: {str(e)[:100]}")
                    search_context = None

            situation = self.pipeline.stage1_situation_extraction(original_input)
            self.signals.log_message.emit(
                f"Situation: {situation.get('title', 'Unknown')}"
            )

            # Stage 2: Generate personas with web search context if available
            self.signals.progress.emit("Stage 2: Persona Generation")
            personas = self.pipeline.stage2_persona_generation(
                situation, original_input, search_context=search_context
            )

            for persona in personas:
                self.signals.persona_added.emit(persona)
                self.signals.progress.emit(
                    f"Generated: {persona.get('name', 'Unknown')}"
                )
                self.signals.progress.emit(
                    f"Generated: {persona.get('name', 'Unknown')}"
                )

            # Stage 3: Run debate rounds based on mode
            self.signals.progress.emit("Stage 3: Debate Rounds")
            try:
                round_history = []
                initial_positions = None

                if self.debate_mode == "sequential":
                    self.signals.progress.emit(
                        f"Sequential Debate Mode ({self.num_rounds} rounds)"
                    )
                    for round_num in range(1, self.num_rounds + 1):
                        self.signals.progress.emit(
                            f"Running Sequential Round {round_num}/{self.num_rounds}"
                        )

                        # Run sequential round
                        round_data, converged = self.pipeline.stage3_sequential_round(
                            personas=personas,
                            situation=situation,
                            round_history=round_history,
                            current_round=round_num,
                            total_rounds=self.num_rounds,
                            include_initial_positions=(round_num == 1),
                            initial_positions=initial_positions,
                            search_context=search_context,
                        )

                        # Compress round data for history
                        compressed_round = self.pipeline.stage4_round_compression(
                            round_data=round_data, round_num=round_num
                        )

                        round_history.append(compressed_round)

                        if converged:
                            self.signals.progress.emit(
                                f"Debate converged at round {round_num}"
                            )
                            break

                else:
                    # Simultaneous mode - use a default of 3 rounds (typical for simultaneous)
                    num_simultaneous_rounds = 3
                    self.signals.progress.emit(
                        f"Simultaneous Debate Mode ({num_simultaneous_rounds} rounds)"
                    )
                    for round_num in range(1, num_simultaneous_rounds + 1):
                        self.signals.progress.emit(
                            f"Running Simultaneous Round {round_num}/{num_simultaneous_rounds}"
                        )

                        round_data = self.pipeline.stage3_simulation_round(
                            personas=personas,
                            situation=situation,
                            round_history=round_history,
                            current_round=round_num,
                            total_rounds=num_simultaneous_rounds,
                            include_initial_positions=(round_num == 1),
                            initial_positions=initial_positions,
                            search_context=search_context,
                        )

                        # Compress round data for history
                        compressed_round = self.pipeline.stage4_round_compression(
                            round_data=round_data, round_num=round_num
                        )

                        round_history.append(compressed_round)

                # Generate report from compressed round history
                self.signals.progress.emit("Stage 4: Report Generation")
                report = self.pipeline.stage5_report_generation(
                    situation=situation,
                    personas=personas,
                    round_history=round_history,
                    initial_positions=initial_positions,
                    original_input=original_input,
                )
                executive_summary = report.get("executive_summary", "")

            except Exception as e:
                error_msg = f"Stage 3/4 failed: {str(e)}"
                log_pipeline_error(
                    "Stage3_4",
                    e,
                    {
                        "mode": self.debate_mode,
                        "num_rounds": self.num_rounds
                        if self.debate_mode == "sequential"
                        else 5,
                        "num_personas": len(personas),
                        "round_history_sample": str(round_history[:2])
                        if round_history
                        else "empty",
                    },
                )
                self.signals.error.emit(
                    (type(e), Exception(error_msg), traceback.format_exc())
                )
                return

            self.signals.result.emit(
                {
                    "situation": situation,
                    "personas": personas,
                    "round_history": round_history,
                    "report": report,
                    "executive_summary": executive_summary,
                }
            )

            self.signals.finished.emit()

        except Exception as e:
            log_pipeline_error("Worker", e, {"situation": self.situation})
            self.signals.error.emit((type(e), e, traceback.format_exc()))


class DeliberateAI(QMainWindow):
    """Main application window for Deliberate AI"""

    def __init__(self):
        super().__init__()

        # Window setup
        self.setWindowTitle("Deliberate AI: Multi-Perspective Decision Analysis")
        self.setGeometry(100, 100, 1400, 900)

        # Initialize state
        self.settings = self.load_settings()
        self.current_mode = "question"
        self.context_data = None
        self.selected_scenario = None
        # Initialize pipeline with settings
        self.pipeline = Pipeline(
            endpoint_url=self.settings.get(
                "vllm_endpoint_url", "http://localhost:8000/v1"
            ),
            model_name=self.settings.get("model_name", "default"),
            api_key=self.settings.get("api_key", "empty"),
        )
        self.is_running = False
        self.search_reachable = True  # Assume web search is reachable
        self.search_enabled = self.settings.get(
            "search_enabled", False
        )  # Default from settings
        self.debate_mode = "simultaneous"  # sequential or simultaneous
        self.num_rounds = 5  # Number of rounds for sequential mode
        self.chat_history = {}
        self.current_persona = None
        self.current_session_name = None
        self.current_question = None
        self.current_report = None
        self.current_personas = []
        self.current_executive_summary = ""
        self.is_generating_response = False

        # TTS state
        self.current_tts_playback = None
        self.is_playing_tts = False
        self.tts_audio_buffer = None
        self.tts_sample_rate = None

        # Window resize tracking
        self._original_geometry = None
        self._is_expanded = False

        # Thread pool for background tasks
        self.threadpool = QThreadPool()
        thread_count = self.threadpool.maxThreadCount()
        print(f"Multithreading with maximum {thread_count} threads")

        # Setup UI
        self.init_ui()

        # Setup status bar timer
        self.status_timer = QTimer()
        self.status_timer.setInterval(1000)
        self.status_timer.timeout.connect(self.update_status_bar)
        self.status_timer.start()

    def closeEvent(self, event):
        """Handle application close - clean up TTS audio files"""
        try:
            # Stop any currently playing TTS
            tts_client = get_tts_client()
            if tts_client and tts_client.is_playing:
                tts_client.stop()

            # Clean up old TTS audio files (older than 24 hours)
            TTSClient.cleanup_tts_folder()
            print("[UI] TTS audio folder cleaned up", file=sys.stderr)
        except Exception as e:
            print(f"[UI] Error during cleanup: {e}", file=sys.stderr)

        # Accept the close event
        event.accept()

    def init_ui(self):
        """Initialize the main UI layout"""
        # Central widget
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # Main layout with splitter for resizable panels
        main_layout = QHBoxLayout(central_widget)

        # Create splitter for resizable panels
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Sidebar
        left_panel = self.create_left_panel()
        splitter.addWidget(left_panel)

        # Center Panel
        center_panel = self.create_center_panel()
        splitter.addWidget(center_panel)

        # Right Panel with tabs
        right_panel = self.create_right_panel()
        splitter.addWidget(right_panel)

        # Set initial sizes
        splitter.setSizes([300, 600, 500])

        main_layout.addWidget(splitter)

        # Setup status bar
        self.status_bar = QStatusBar()
        self.setStatusBar(self.status_bar)
        self.status_bar.showMessage("Ready")

    def create_left_panel(self):
        """Create the left sidebar panel"""
        panel = QFrame()
        panel.setFixedWidth(320)
        panel.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border-right: 1px solid #444;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setSpacing(12)
        layout.setContentsMargins(15, 15, 15, 15)

        # Title
        title = QLabel("Deliberate AI")
        title.setFont(QFont("Arial", 18, QFont.Weight.Bold))
        title.setStyleSheet("color: #3B8ED0; padding: 10px;")
        layout.addWidget(title)

        # Input mode selector
        mode_group = QGroupBox("Input Mode")
        mode_layout = QVBoxLayout(mode_group)
        mode_layout.setSpacing(5)

        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["Question", "Document", "YAML"])
        self.mode_combo.currentTextChanged.connect(self.on_mode_change)
        mode_layout.addWidget(self.mode_combo)

        layout.addWidget(mode_group)

        # Debate mode selector
        debate_group = QGroupBox("Debate Mode")
        debate_scroll = QScrollArea()
        debate_scroll.setWidgetResizable(True)
        debate_scroll.setFrameShape(QScrollArea.Shape.NoFrame)
        debate_scroll.setMaximumHeight(130)
        debate_scroll.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)

        debate_widget = QWidget()
        debate_layout = QVBoxLayout(debate_widget)
        debate_layout.setSpacing(6)
        debate_layout.setContentsMargins(0, 0, 0, 0)

        self.debate_mode_combo = QComboBox()
        self.debate_mode_combo.addItems(["Simultaneous", "Sequential (3-10 rounds)"])
        self.debate_mode_combo.setMinimumHeight(28)
        self.debate_mode_combo.currentTextChanged.connect(self.on_debate_mode_change)
        debate_layout.addWidget(self.debate_mode_combo)

        # Rounds slider (only relevant for sequential mode)
        self.rounds_label = QLabel("5 rounds")
        self.rounds_label.setStyleSheet("color: #888888; font-size: 10px;")
        self.rounds_label.setAlignment(Qt.AlignmentFlag.AlignLeft)

        self.rounds_slider = QSlider(Qt.Orientation.Horizontal)
        self.rounds_slider.setMinimum(3)
        self.rounds_slider.setMaximum(10)
        self.rounds_slider.setValue(5)
        self.rounds_slider.setTickPosition(QSlider.TickPosition.TicksBelow)
        self.rounds_slider.setTickInterval(1)
        self.rounds_slider.setStyleSheet("""
            QSlider::groove:horizontal {
                border: 1px solid #444;
                height: 8px;
                background: #2a2a2a;
                border-radius: 4px;
            }
            QSlider::handle:horizontal {
                background: #3B8ED0;
                border: 1px solid #1E6FA9;
                width: 16px;
                height: 16px;
                margin: -4px 0;
                border-radius: 8px;
            }
            QSlider::handle:horizontal:hover {
                background: #1E6FA9;
            }
        """)
        self.rounds_slider.valueChanged.connect(self.update_rounds_label)

        debate_layout.addWidget(self.rounds_label)
        debate_layout.addWidget(self.rounds_slider)
        debate_layout.addStretch()

        debate_scroll.setWidget(debate_widget)
        layout.addWidget(debate_scroll)

        # Web search option
        search_group = QGroupBox("Web Search / Fact-Check")
        search_layout = QVBoxLayout(search_group)
        search_layout.setSpacing(5)

        self.search_checkbox = QCheckBox("Enable web search between debate rounds")
        self.search_checkbox.setChecked(False)
        self.search_checkbox.stateChanged.connect(self.on_search_toggle)
        search_layout.addWidget(self.search_checkbox)

        search_info = QLabel(
            "When enabled, the system will search for facts and validate claims between debate rounds"
        )
        search_info.setWordWrap(True)
        search_info.setStyleSheet("color: #888888; font-size: 10px;")
        search_info.setContentsMargins(10, 0, 0, 0)
        search_layout.addWidget(search_info)

        layout.addWidget(search_group)

        # Input text area
        input_group = QGroupBox("Scenario")
        input_layout = QVBoxLayout(input_group)
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(0)

        # Create a scroll area wrapper
        scroll_wrapper = QScrollArea()
        scroll_wrapper.setWidgetResizable(True)
        scroll_wrapper.setFrameShape(QScrollArea.Shape.NoFrame)
        scroll_wrapper.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )
        scroll_wrapper.setStyleSheet("""
            QScrollArea {
                background-color: transparent;
                border: none;
            }
        """)

        # Container widget for the text edit
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        text_layout.setSpacing(0)

        self.input_text = QTextEdit()
        self.input_text.setPlaceholderText(
            "Enter your decision question or scenario..."
        )
        self.input_text.setMinimumHeight(180)
        self.input_text.setMaximumHeight(250)
        self.input_text.setAcceptRichText(False)
        self.input_text.setLineWrapMode(QTextEdit.LineWrapMode.WidgetWidth)
        self.input_text.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 10px;
                padding-bottom: 20px;
            }
        """)

        text_layout.addWidget(self.input_text)
        scroll_wrapper.setWidget(text_container)
        input_layout.addWidget(scroll_wrapper)

        layout.addWidget(input_group)

        # Buttons
        self.run_btn = QPushButton("Run Simulation")
        self.run_btn.setMinimumHeight(40)
        self.run_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B8ED0;
                color: white;
                font-weight: bold;
                font-size: 14px;
                border-radius: 4px;
                padding: 10px;
            }
            QPushButton:hover {
                background-color: #1E6FA9;
            }
            QPushButton:disabled {
                background-color: #555555;
            }
        """)
        self.run_btn.clicked.connect(self.run_simulation)
        layout.addWidget(self.run_btn)

        self.new_sim_btn = QPushButton("New Simulation")
        self.new_sim_btn.setMinimumHeight(35)
        self.new_sim_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        self.new_sim_btn.clicked.connect(self.new_simulation)
        layout.addWidget(self.new_sim_btn)

        self.settings_btn = QPushButton("Settings")
        self.settings_btn.setMinimumHeight(35)
        self.settings_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                border-radius: 4px;
                padding: 8px;
            }
            QPushButton:hover {
                background-color: #666666;
            }
        """)
        self.settings_btn.clicked.connect(self.open_settings)
        layout.addWidget(self.settings_btn)

        layout.addStretch()

        return panel

    def create_center_panel(self):
        """Create the center panel for input and progress"""
        panel = QFrame()
        panel.setStyleSheet("""
            QFrame {
                background-color: #1a1a1a;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setSpacing(10)
        layout.setContentsMargins(10, 10, 10, 10)

        # Progress log
        progress_group = QGroupBox("Simulation Progress")
        progress_layout = QVBoxLayout(progress_group)

        self.progress_log = QTextEdit()
        self.progress_log.setReadOnly(True)
        self.progress_log.setMinimumHeight(400)
        self.progress_log.setStyleSheet("""
            QTextEdit {
                background-color: #0a0a0a;
                color: #00ff00;
                font-family: 'Consolas', 'Monospace';
                font-size: 11px;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        progress_layout.addWidget(self.progress_log)

        layout.addWidget(progress_group)

        layout.addStretch()

        return panel

    def create_right_panel(self):
        """Create the right panel with tabs"""
        panel = QFrame()
        panel.setFixedWidth(500)
        panel.setStyleSheet("""
            QFrame {
                background-color: #2a2a2a;
                border-left: 1px solid #444;
            }
        """)

        layout = QVBoxLayout(panel)
        layout.setSpacing(5)
        layout.setContentsMargins(10, 10, 10, 10)

        # Header
        header = QLabel("SIMULATION RESULTS")
        header.setFont(QFont("Arial", 14, QFont.Weight.Bold))
        header.setStyleSheet("color: #3B8ED0; padding: 5px;")
        layout.addWidget(header)

        # Tab widget
        self.tab_widget = QTabWidget()
        self.tab_widget.setStyleSheet("""
            QTabWidget::pane {
                border: 1px solid #444;
                background-color: #1a1a1a;
                border-radius: 4px;
            }
            QTabBar::tab {
                background-color: #333333;
                color: #e0e0e0;
                padding: 8px 16px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
                margin-right: 2px;
            }
            QTabBar::tab:selected {
                background-color: #3B8ED0;
                color: white;
            }
            QTabBar::tab:hover:!selected {
                background-color: #444444;
            }
        """)

        # Report Tab
        report_widget = self.create_report_tab()
        self.tab_widget.addTab(report_widget, "Report")

        # Chat Tab
        chat_widget = self.create_chat_tab()
        self.tab_widget.addTab(chat_widget, "Persona Chat")

        layout.addWidget(self.tab_widget)

        return panel

    def create_report_tab(self):
        """Create the report tab content"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)

        # Scrollable report area
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("""
            QScrollArea {
                border: 1px solid #444;
                background-color: #1a1a1a;
                border-radius: 4px;
            }
        """)

        self.report_content = QTextEdit()
        self.report_content.setReadOnly(True)
        self.report_content.setStyleSheet("""
            QTextEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: none;
                padding: 10px;
                font-size: 11px;
                line-height: 1.5;
            }
        """)

        scroll.setWidget(self.report_content)
        layout.addWidget(scroll)

        # TTS Controls Section
        tts_group = QGroupBox("🔊 Text-to-Speech")
        tts_layout = QHBoxLayout()

        # Voice selector
        tts_layout.addWidget(QLabel("Voice:"))
        self.tts_report_voice_combo = QComboBox()
        # Initialize TTS client to get available voices
        client = get_tts_client()
        self.tts_report_voice_combo.addItems(client.available_voices)
        self.tts_report_voice_combo.setCurrentText("af_bella")
        self.tts_report_voice_combo.setEnabled(True)
        tts_layout.addWidget(self.tts_report_voice_combo)

        # Device indicator
        self.tts_device_label = QLabel("🔊 Kokoro PyTorch TTS (CUDA GPU)")
        self.tts_device_label.setStyleSheet("color: #888; font-size: 10px;")
        self.tts_device_label.setFixedWidth(120)
        tts_layout.addWidget(self.tts_device_label)

        # Play/Stop buttons
        self.tts_play_report_btn = QPushButton("▶ Play")
        self.tts_play_report_btn.setEnabled(False)
        self.tts_play_report_btn.setFixedWidth(80)
        self.tts_play_report_btn.clicked.connect(self.play_report_tts)

        self.tts_stop_report_btn = QPushButton("⏹ Stop")
        self.tts_stop_report_btn.setEnabled(False)
        self.tts_stop_report_btn.setFixedWidth(70)
        self.tts_stop_report_btn.clicked.connect(self.stop_tts)

        # Status label
        self.tts_status_label = QLabel("Ready")
        self.tts_status_label.setStyleSheet("color: #888; font-size: 10px;")
        self.tts_status_label.setFixedWidth(100)

        tts_layout.addWidget(self.tts_play_report_btn)
        tts_layout.addWidget(self.tts_stop_report_btn)
        tts_layout.addStretch()
        tts_layout.addWidget(self.tts_status_label)

        tts_group.setLayout(tts_layout)
        layout.addWidget(tts_group)

        # Save buttons
        button_layout = QHBoxLayout()

        save_report_btn = QPushButton("Save Report")
        save_report_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B8ED0;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: #1E6FA9;
            }
        """)
        save_report_btn.clicked.connect(self.save_report)
        button_layout.addWidget(save_report_btn)

        save_summary_btn = QPushButton("Save Summary")
        save_summary_btn.setEnabled(False)
        save_summary_btn.setStyleSheet("""
            QPushButton {
                background-color: #555555;
                color: white;
                padding: 8px;
                border-radius: 4px;
            }
        """)
        save_summary_btn.clicked.connect(self.save_executive_summary)
        button_layout.addWidget(save_summary_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        return widget

    def create_chat_tab(self):
        """Create the persona chat tab content"""
        widget = QWidget()
        layout = QVBoxLayout(widget)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(10)

        # Persona selector
        selector_layout = QHBoxLayout()
        selector_layout.addWidget(QLabel("Select Persona:"))

        self.persona_selector = QComboBox()
        self.persona_selector.setEnabled(False)
        self.persona_selector.currentTextChanged.connect(self.on_persona_select)
        selector_layout.addWidget(self.persona_selector)

        layout.addLayout(selector_layout)

        # Session controls
        session_layout = QHBoxLayout()

        self.new_session_btn = QPushButton("New Session")
        self.new_session_btn.setEnabled(
            True
        )  # Enable by default - can always start new session
        self.new_session_btn.clicked.connect(self.new_chat_session)
        session_layout.addWidget(self.new_session_btn)

        self.save_session_btn = QPushButton("Save Session")
        self.save_session_btn.setEnabled(
            True
        )  # Enable by default - can save empty or partial sessions
        self.save_session_btn.clicked.connect(self.save_chat_session)
        session_layout.addWidget(self.save_session_btn)

        self.load_session_btn = QPushButton("Load Session")
        self.load_session_btn.setEnabled(
            True
        )  # Enable by default - can always load saved sessions
        self.load_session_btn.clicked.connect(self.load_chat_session)
        session_layout.addWidget(self.load_session_btn)

        session_layout.addStretch()
        layout.addLayout(session_layout)

        # Session info
        self.session_info_label = QLabel("Session: None")
        self.session_info_label.setStyleSheet("color: #888888; font-size: 11px;")
        layout.addWidget(self.session_info_label)

        # Web search toggle
        search_layout = QHBoxLayout()
        self.chat_search_checkbox = QCheckBox(
            "Enable smart web search for current facts"
        )
        self.chat_search_checkbox.setChecked(self.settings.get("search_enabled", False))
        self.chat_search_checkbox.stateChanged.connect(self.on_chat_search_toggle)
        self.chat_search_checkbox.setStyleSheet("color: #e0e0e0; font-size: 11px;")
        search_layout.addWidget(self.chat_search_checkbox)
        search_layout.addStretch()
        layout.addLayout(search_layout)

        # Search status indicator
        self.search_status_label = QLabel("")
        self.search_status_label.setFixedHeight(18)
        self.search_status_label.setStyleSheet("color: #00ff00; font-size: 10px;")
        layout.addWidget(self.search_status_label)

        # Persona details
        self.persona_details_label = QLabel("Select a persona to start chatting...")
        self.persona_details_label.setWordWrap(True)
        self.persona_details_label.setStyleSheet("""
            QLabel {
                background-color: #2a2a2a;
                padding: 8px;
                border-radius: 4px;
                border: 1px solid #444;
            }
        """)
        layout.addWidget(self.persona_details_label)

        # Chat display
        # Chat display - use QTextBrowser for link support
        self.chat_display = QTextBrowser()
        self.chat_display.setReadOnly(True)
        self.chat_display.setOpenLinks(False)  # We'll handle links manually
        self.chat_display.anchorClicked.connect(self.handle_chat_anchor_click)
        self.chat_display.setStyleSheet("""
            QTextBrowser {
                background-color: #0a0a0a;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 8px;
                font-size: 11px;
            }
            QTextBrowser a {
                color: #3B8ED0;
                text-decoration: none;
            }
            QTextBrowser a:hover {
                text-decoration: underline;
            }
        """)
        layout.addWidget(self.chat_display)

        # Input area
        input_layout = QHBoxLayout()

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type your message to the persona...")
        self.chat_input.returnPressed.connect(self.send_message)
        self.chat_input.setStyleSheet("""
            QLineEdit {
                background-color: #1a1a1a;
                color: #e0e0e0;
                border: 1px solid #444;
                border-radius: 4px;
                padding: 8px;
            }
        """)
        input_layout.addWidget(self.chat_input)

        self.send_btn = QPushButton("Send")
        self.send_btn.setEnabled(False)
        self.send_btn.clicked.connect(self.send_message)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3B8ED0;
                color: white;
                padding: 8px 16px;
                border-radius: 4px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #1E6FA9;
            }
            QPushButton:disabled {
                background-color: #555555;
            }
        """)
        input_layout.addWidget(self.send_btn)

        layout.addLayout(input_layout)

        return widget

    def on_mode_change(self, mode):
        """Handle input mode change"""
        self.current_mode = mode

    def on_debate_mode_change(self, mode):
        """Handle debate mode change"""
        if "Sequential" in mode:
            self.debate_mode = "sequential"
            self.rounds_slider.setEnabled(True)
        else:
            self.debate_mode = "simultaneous"
            self.rounds_slider.setEnabled(False)
            # Reset num_rounds to default for simultaneous mode
            self.num_rounds = 3

    def update_rounds_label(self, value):
        """Update the rounds label when slider changes"""
        self.rounds_label.setText(f"{value} round{'s' if value != 1 else ''}")
        self.num_rounds = value  # Store the number of rounds
        self.debate_mode = "sequential"  # Ensure we're in sequential mode

    def on_search_toggle(self, state):
        """Handle web search toggle for simulation"""
        self.search_enabled = state == Qt.CheckState.Checked.value

    def on_chat_search_toggle(self, state):
        """Handle web search toggle for persona chat"""
        # This will be used by PersonaResponseWorker
        pass

    def log_progress(self, message):
        """Log a message to the progress display"""
        self.progress_log.append(message)
        self.progress_log.ensureCursorVisible()

    def update_status_bar(self):
        """Update status bar with current time"""
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.status_bar.showMessage(f"Ready | {current_time}")

    def load_settings(self):
        """Load settings from JSON file"""
        try:
            with open("settings.json", "r") as f:
                return json.load(f)
        except:
            return {"model": "default", "temperature": 0.7}

    def save_settings(self, settings):
        """Save settings to JSON file"""
        with open("settings.json", "w") as f:
            json.dump(settings, f, indent=2)

    def new_simulation(self):
        """Start a new simulation"""
        self.input_text.clear()
        self.progress_log.clear()
        self.report_content.clear()
        self.chat_display.clear()
        self.current_personas = []
        self.persona_selector.clear()
        self.persona_selector.setEnabled(False)
        self.send_btn.setEnabled(False)

    def run_simulation(self):
        """Run the simulation in a background thread"""
        if self.is_running:
            QMessageBox.warning(self, "Warning", "Simulation is already running")
            return

        user_input = self.input_text.toPlainText().strip()
        if not user_input:
            QMessageBox.warning(self, "Warning", "Please enter a question or scenario")
            return

        self.is_running = True
        self.run_btn.setEnabled(False)
        self.log_progress("Starting simulation...")
        self.log_progress(f"Mode: {self.debate_mode.capitalize()}")
        if self.debate_mode == "sequential":
            self.log_progress(f"Number of Rounds: {self.num_rounds}")
        else:
            self.log_progress("Number of Rounds: 3 (default for simultaneous)")
        self.log_progress(
            f"Web Search: {'Enabled' if self.search_enabled else 'Disabled'}"
        )

        # Create worker
        worker = SimulationWorker(
            {"question": user_input},
            self.pipeline,
            self.settings,
            self.search_reachable,
            self.debate_mode,
            self.num_rounds,
        )

        # Connect signals
        worker.signals.progress.connect(self.log_progress)
        worker.signals.persona_added.connect(self.add_persona_live)
        worker.signals.result.connect(self.on_simulation_complete)
        worker.signals.error.connect(self.on_simulation_error)
        worker.signals.finished.connect(self.on_simulation_finished)

        # Start worker
        self.threadpool.start(worker)

    def on_simulation_complete(self, result):
        """Handle simulation completion"""
        self.current_question = result["situation"].get("question", "")
        self.current_personas = result["personas"]
        self.current_report = result["report"]
        self.current_executive_summary = result["executive_summary"]

        # Display report
        self.display_report(result["report"])

        # Enable chat
        self.persona_selector.clear()
        for persona in result["personas"]:
            self.persona_selector.addItem(persona.get("name", "Unknown"))
        self.persona_selector.setEnabled(True)
        self.send_btn.setEnabled(True)

        if result["personas"]:
            self.persona_selector.setCurrentIndex(0)
            self.on_persona_select(result["personas"][0].get("name", ""))

    def on_simulation_error(self, error):
        """Handle simulation error"""
        error_type = error[0].__name__ if error[0] else "Unknown"
        error_msg = str(error[1])
        error_traceback = error[2] if len(error) > 2 else ""

        # Log the error
        log_ui_error("Simulation", error[1], {"type": error_type})

        # Show detailed error message
        error_dialog = QMessageBox(self)
        error_dialog.setWindowTitle(f"Simulation Error: {error_type}")
        error_dialog.setIcon(QMessageBox.Icon.Critical)

        # Format error message
        message = f"<b>{error_msg}</b><br><br>"
        if error_traceback:
            message += f"<details><summary>View traceback</summary><pre style='background:#222;color:#0f0;padding:10px;text-align:left;'>{error_traceback}</pre></details>"

        error_dialog.setText(message)
        error_dialog.setStandardButtons(QMessageBox.StandardButton.Ok)
        error_dialog.exec()

        self.log_progress(f"ERROR [{error_type}]: {error_msg}")
        self.is_running = False
        self.run_btn.setEnabled(True)

    def on_simulation_finished(self):
        """Handle simulation finished"""
        self.is_running = False
        self.run_btn.setEnabled(True)

    def add_persona_live(self, persona):
        """Add a persona to the live display"""
        self.log_progress(f"--- NEW PERSONA ---")
        self.log_progress(f"Name: {persona.get('name', 'Unknown')}")
        self.log_progress(f"Role: {persona.get('role_title', 'Unknown')}")
        self.log_progress(f"Organization: {persona.get('organization', 'Unknown')}")
        self.log_progress(f"Approach: {persona.get('approach', 'Unknown')}")
        self.log_progress(f"Worldview: {persona.get('worldview', '')}")
        self.log_progress(f"Initial Position: {persona.get('initial_position', '')}\n")

    def display_report(self, report):
        """Display the simulation report"""
        if not report:
            return

        md_content = "# Deliberate AI Report\n\n"
        md_content += f"**Question:** {self.current_question}\n\n"

        # Add "What's Being Considered" at top
        if "question_analyzed" in report:
            md_content += "## What's Being Considered\n\n"
            md_content += str(report.get("question_analyzed", "")) + "\n\n"

        for key, value in report.items():
            if key == "question_analyzed":
                continue
            md_content += f"## {key.replace('_', ' ').title()}\n\n"
            if isinstance(value, list):
                md_content += "\n".join(f"- {str(item)}" for item in value) + "\n\n"
            else:
                md_content += f"{str(value)}\n\n"

        self.report_content.setText(md_content)
        self.current_report = report

        # Enable TTS button if report has content
        if md_content and len(md_content) > 100:
            self.tts_play_report_btn.setEnabled(True)
            self.tts_stop_report_btn.setEnabled(False)
            self.tts_report_voice_combo.setEnabled(True)

        # Automatically save report to reports folder
        self._auto_save_report(report)

    def send_message(self):
        """Send message to selected persona using non-blocking thread"""
        if not self.current_persona:
            return

        user_message = self.chat_input.text().strip()
        if not user_message:
            return

        # Prevent multiple simultaneous requests
        if self.is_generating_response:
            QMessageBox.warning(
                self, "Warning", "Please wait for the current response to complete."
            )
            return

        # Display user message
        self.chat_display.append(f"\n<b>You:</b> {user_message}<br>")
        self.chat_display.ensureCursorVisible()

        # Clear the input field immediately
        self.chat_input.clear()

        # Disable send button and show loading state
        self.send_btn.setEnabled(False)
        self.chat_input.setEnabled(False)
        self.is_generating_response = True

        # Get persona data
        persona = None
        for p in self.current_personas:
            if p.get("name") == self.current_persona:
                persona = p
                break

        # If persona not found in current simulation, create a minimal persona from loaded session
        if not persona and self.current_persona:
            # Create a minimal persona object for loaded sessions
            persona = {
                "name": self.current_persona,
                "role_title": "Loaded Persona",
                "organization": "Saved Session",
                "approach": "Based on previous analysis",
                "background": "This persona was from a previously saved conversation",
                "initial_position": "Continuing previous conversation",
                "role_type": "Loaded",
            }

        if not persona:
            self.chat_display.append("<b>Error:</b> Persona not found<br>")
            self.chat_display.ensureCursorVisible()
            self.send_btn.setEnabled(True)
            self.chat_input.setEnabled(True)
            self.is_generating_response = False
            return

        # Get prediction
        predicted_outcome = ""
        if hasattr(self, "current_report") and self.current_report:
            predicted_outcome = self.current_report.get(
                "predicted_outcome", "No prediction available"
            )

        # Get chat history for this persona (excluding the current message)
        persona_chat_history = []
        if self.current_persona in self.chat_history:
            persona_chat_history = self.chat_history[self.current_persona]

        # Check if web search is enabled for chat
        search_enabled = self.chat_search_checkbox.isChecked()

        # Start worker thread with chat history and search setting
        worker = PersonaResponseWorker(
            persona,
            user_message,  # Pass the actual user message text
            self.pipeline,
            self.current_question,
            predicted_outcome,
            persona_chat_history,
            search_enabled=search_enabled,  # Pass search setting
        )

        worker.signals.result.connect(self.on_persona_response)
        worker.signals.error.connect(self.on_persona_error)
        worker.signals.finished.connect(self.on_persona_finished)

        # Store the user message for saving to history
        self._last_user_message = user_message

        self.threadpool.start(worker)

    def on_persona_response(self, response):
        """Handle persona response - format dictionary responses cleanly"""

        # Check if response is a dictionary (structured response)
        if isinstance(response, dict):
            # Format the response nicely
            formatted_response = self._format_persona_response(response)
        else:
            # Use response as-is (plain text)
            formatted_response = str(response)

        # Display formatted response with TTS link
        # Use a unique message ID based on timestamp
        import time

        message_id = f"msg_{int(time.time() * 1000)}"

        # Store message text for TTS
        if not hasattr(self, "_tts_messages"):
            self._tts_messages = {}
        self._tts_messages[message_id] = formatted_response

        # Create HTML with TTS link (using custom scheme)
        tts_link_html = f'<a href="tts:{message_id}" style="text-decoration:none;" title="Listen to message">🔊</a>'

        self.chat_display.append(
            f"<b>{self.current_persona}:</b><br>{formatted_response} {tts_link_html}<br>"
        )
        self.chat_display.ensureCursorVisible()

        # Save to history
        if self.current_persona not in self.chat_history:
            self.chat_history[self.current_persona] = []

        if hasattr(self, "_last_user_message"):
            self.chat_history[self.current_persona].append(
                {"role": "You", "text": self._last_user_message}
            )
        self.chat_history[self.current_persona].append(
            {"role": self.current_persona, "text": formatted_response}
        )
        self.chat_display.ensureCursorVisible()

        # Store message text for TTS
        if not hasattr(self, "_tts_messages"):
            self._tts_messages = {}
        self._tts_messages[message_id] = formatted_response

        # Save to history - use the user_message that was passed to the worker
        # The worker stores it in self.user_message
        if self.current_persona not in self.chat_history:
            self.chat_history[self.current_persona] = []

        # We need to get the user message from the last worker - but we don't have direct access
        # Instead, we'll store it in a temporary attribute before starting the worker
        # For now, we'll just skip saving the user message since it's already displayed
        # Actually, let's fix this properly by storing the last user message
        if hasattr(self, "_last_user_message"):
            self.chat_history[self.current_persona].append(
                {"role": "You", "text": self._last_user_message}
            )
        self.chat_history[self.current_persona].append(
            {"role": self.current_persona, "text": formatted_response}
        )

    def _format_persona_response(self, response_dict):
        """Format a dictionary response into clean HTML"""
        html_parts = []

        # Extract fields with fallbacks
        role = response_dict.get("role", response_dict.get("persona", "Unknown"))
        title = response_dict.get("title", "")
        institution = response_dict.get("institution", "")
        assessment = response_dict.get("assessment", response_dict.get("response", ""))
        predicted_outcome = response_dict.get("predicted_outcome", "")
        recommendation = response_dict.get("recommendation", "")

        # Build formatted HTML
        if title or institution:
            header = f"<i>{role}</i><br>"
            if title:
                header += f"<b>{title}</b><br>"
            if institution:
                header += f"<i>{institution}</i><br><br>"
            html_parts.append(header)

        # Assessment section
        if assessment:
            html_parts.append("<b>Assessment:</b><br>" + assessment + "<br>")

        # Predicted outcome section
        if predicted_outcome:
            html_parts.append(
                "<br><b>Predicted Outcome:</b><br>" + predicted_outcome + "<br>"
            )

        # Recommendation section
        if recommendation:
            html_parts.append("<br><b>Recommendation:</b><br>" + recommendation)

        return "<br>".join(html_parts)

    def on_persona_error(self, error):
        """Handle persona response error"""
        self.chat_display.append(f"<b>Error:</b> {str(error[1])}\n")
        self.chat_display.ensureCursorVisible()

    def on_persona_finished(self):
        """Handle persona response finished"""
        self.send_btn.setEnabled(True)
        self.chat_input.setEnabled(True)
        self.chat_input.setFocus()
        self.is_generating_response = False

    def on_persona_select(self, persona_name):
        """Handle persona selection"""
        self.current_persona = persona_name
        self.send_btn.setEnabled(True)
        self.new_session_btn.setEnabled(True)
        self.save_session_btn.setEnabled(True)
        self.load_session_btn.setEnabled(True)

        # Find persona details
        for persona in self.current_personas:
            if persona.get("name") == persona_name:
                self.display_persona_details(persona)
                self.load_chat_history(persona_name)
                break

    def display_persona_details(self, persona):
        """Display persona details"""
        details = f"""
<b>{persona.get("name", "Unknown")}</b><br>
<b>Role:</b> {persona.get("role_title", "Unknown")}<br>
<b>Organization:</b> {persona.get("organization", "Unknown")}<br>
<b>Approach:</b> {persona.get("approach", "Unknown")}<br>
<b>Background:</b> {persona.get("background", "")[:200]}...
"""
        self.persona_details_label.setText(details)

    def display_persona_details_for_loaded_session(self, persona_name, question):
        """Display persona details for a loaded session (when persona is not in current simulation)"""
        # For loaded sessions, we show the persona name and the question they were created for
        details = f"""
<b>{persona_name}</b><br>
<b>Session Question:</b> {question if question else "Unknown"}<br>
<br>
<i>This persona was from a previous simulation. Chat with them based on their perspective from that analysis.</i>
"""
        self.persona_details_label.setText(details)

    def load_chat_history(self, persona_name):
        """Load chat history for persona"""
        self.chat_display.clear()
        if persona_name in self.chat_history and self.chat_history[persona_name]:
            for message in self.chat_history[persona_name]:
                self.chat_display.append(
                    f"\n<b>{message['role']}:</b> {message['text']}\n"
                )
        else:
            self.chat_display.append("Start a conversation with this persona...\n")

    def new_chat_session(self):
        """Start a new chat session"""
        if self.current_persona:
            self.chat_history[self.current_persona] = []
            self.chat_display.clear()
            self.chat_display.append("Start a new conversation...\n")
            self.session_info_label.setText("Session: New")

    def save_chat_session(self):
        """Save current chat session"""
        if not self.current_persona:
            QMessageBox.warning(self, "Warning", "No persona selected")
            return

        filename = QFileDialog.getSaveFileName(
            self,
            "Save Chat Session",
            f"saved_sessions/{self.current_persona}.json",
            "JSON files (*.json)",
        )[0]

        if filename:
            try:
                session_data = {
                    "persona": self.current_persona,
                    "question": self.current_question,
                    "history": self.chat_history.get(self.current_persona, []),
                }
                with open(filename, "w") as f:
                    json.dump(session_data, f, indent=2)
                QMessageBox.information(self, "Success", f"Session saved to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save session: {str(e)}")

    def load_chat_session(self):
        """Load a saved chat session"""
        filename = QFileDialog.getOpenFileName(
            self, "Load Chat Session", "saved_sessions", "JSON files (*.json)"
        )[0]

        if filename:
            try:
                with open(filename, "r") as f:
                    session_data = json.load(f)

                loaded_persona = session_data.get("persona", "")
                loaded_history = session_data.get("history", [])
                loaded_question = session_data.get("question", "")

                if not loaded_persona:
                    QMessageBox.warning(
                        self, "Warning", "No persona found in saved session"
                    )
                    return

                # Set the current persona and chat history
                self.current_persona = loaded_persona
                self.chat_history[loaded_persona] = loaded_history
                self.current_question = loaded_question

                # Update selector - add persona if not already in list
                current_items = [
                    self.persona_selector.itemText(i)
                    for i in range(self.persona_selector.count())
                ]
                if loaded_persona not in current_items:
                    self.persona_selector.addItem(loaded_persona)

                # Select the loaded persona
                self.persona_selector.setCurrentText(loaded_persona)

                # Manually display persona details and chat history
                self.display_persona_details_for_loaded_session(
                    loaded_persona, loaded_question
                )

                # Display chat
                self.chat_display.clear()
                if loaded_history:
                    for message in loaded_history:
                        self.chat_display.append(
                            f"\n<b>{message['role']}:</b> {message['text']}\n"
                        )
                else:
                    self.chat_display.append(
                        "Start a conversation with this persona...\n"
                    )

                self.session_info_label.setText(
                    f"Session: {os.path.basename(filename)}"
                )

                # Enable session control buttons
                self.new_session_btn.setEnabled(True)
                self.save_session_btn.setEnabled(True)
                self.load_session_btn.setEnabled(True)
                self.send_btn.setEnabled(True)

                QMessageBox.information(
                    self, "Success", f"Loaded session: {os.path.basename(filename)}"
                )
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to load session: {str(e)}")

    def save_report(self):
        """Save the full report to a file"""
        if not self.current_report:
            QMessageBox.warning(self, "Warning", "No report to save")
            return

        filename = QFileDialog.getSaveFileName(
            self,
            "Save Report",
            f"reports/report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            "JSON files (*.json)",
        )[0]

        if filename:
            try:
                with open(filename, "w") as f:
                    json.dump(self.current_report, f, indent=2)
                QMessageBox.information(self, "Success", f"Report saved to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save report: {str(e)}")

    def save_executive_summary(self):
        """Save the executive summary to a file"""
        if not self.current_executive_summary:
            QMessageBox.warning(self, "Warning", "No executive summary to save")
            return

        filename = QFileDialog.getSaveFileName(
            self,
            "Save Executive Summary",
            f"reports/summary_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text files (*.txt)",
        )[0]

        if filename:
            try:
                with open(filename, "w") as f:
                    f.write(self.current_executive_summary)
                QMessageBox.information(self, "Success", f"Summary saved to {filename}")
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Failed to save summary: {str(e)}")

    def _auto_save_report(self, report):
        """Automatically save report to a new folder with all file types"""
        try:
            # Generate timestamp for folder and files
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create folder structure: reports/YYYYMMDD/SIMULATION_NAME/
            # Extract simulation name from question or use timestamp
            sim_name = (
                self.current_question[:50]
                .replace(":", "")
                .replace("/", "-")
                .replace("\\", "-")
                if self.current_question
                else f"simulation_{timestamp}"
            )
            sim_name = "".join(
                c if c.isalnum() or c in " _-" else "" for c in sim_name
            ).strip()

            folder_name = f"{timestamp}_{sim_name}"
            folder_path = os.path.join("reports", folder_name)

            # Create the folder
            os.makedirs(folder_path, exist_ok=True)

            # 1. Save full report as JSON
            json_file = os.path.join(folder_path, "full_report.json")
            with open(json_file, "w") as f:
                json.dump(report, f, indent=2)

            # 2. Save formatted report as Markdown
            md_content = self._generate_markdown_report(report)
            md_file = os.path.join(folder_path, "report.md")
            with open(md_file, "w", encoding="utf-8") as f:
                f.write(md_content)

            # 3. Save executive summary as TXT
            summary = (
                self.current_executive_summary
                if self.current_executive_summary
                else "No executive summary available"
            )
            txt_file = os.path.join(folder_path, "summary.txt")
            with open(txt_file, "w", encoding="utf-8") as f:
                f.write(summary)

            # 4. Save a simple text version of the full report
            text_report = self._generate_text_report(report)
            text_file = os.path.join(folder_path, "report.txt")
            with open(text_file, "w", encoding="utf-8") as f:
                f.write(text_report)

            # Show notification
            self.statusBar().showMessage(f"Report saved to {folder_path}/", 5000)

        except Exception as e:
            print(f"Failed to auto-save report: {e}")

    def _generate_markdown_report(self, report):
        """Generate markdown formatted report"""
        md_content = "# Deliberate AI Report\n\n"
        md_content += f"**Question:** {self.current_question}\n\n"
        md_content += (
            f"**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        )

        # Add "What's Being Considered" at top
        if "question_analyzed" in report:
            md_content += "## What's Being Considered\n\n"
            md_content += str(report.get("question_analyzed", "")) + "\n\n"

        for key, value in report.items():
            if key == "question_analyzed":
                continue
            md_content += f"## {key.replace('_', ' ').title()}\n\n"
            if isinstance(value, list):
                md_content += "\n".join(f"- {str(item)}" for item in value) + "\n\n"
            else:
                md_content += f"{str(value)}\n\n"

        return md_content

    def _generate_text_report(self, report):
        """Generate plain text version of report"""
        text_content = "DELIBERATE AI REPORT\n"
        text_content += "=" * 80 + "\n\n"
        text_content += f"Question: {self.current_question}\n"
        text_content += f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
        text_content += "=" * 80 + "\n\n"

        for key, value in report.items():
            text_content += f"\n{key.replace('_', ' ').upper()}\n"
            text_content += "-" * 40 + "\n"
            if isinstance(value, list):
                for item in value:
                    text_content += f"  - {str(item)}\n"
            else:
                text_content += f"  {str(value)}\n"

        return text_content

    def open_settings(self):
        """Open settings dialog"""
        dialog = QDialog(self)
        dialog.setWindowTitle("Settings")
        dialog.setGeometry(300, 300, 500, 450)

        layout = QVBoxLayout(dialog)

        # vLLM Endpoint URL
        layout.addWidget(QLabel("vLLM Endpoint URL:"))
        endpoint_input = QLineEdit(self.settings.get("vllm_endpoint_url", ""))
        layout.addWidget(endpoint_input)

        # Model Name
        layout.addWidget(QLabel("Model Name:"))
        model_input = QLineEdit(self.settings.get("model_name", ""))
        layout.addWidget(model_input)

        # API Key
        layout.addWidget(QLabel("API Key:"))
        api_input = QLineEdit(self.settings.get("api_key", ""))
        api_input.setEchoMode(QLineEdit.EchoMode.Password)
        layout.addWidget(api_input)

        # Search Enabled
        search_enabled = self.settings.get("search_enabled", False)
        search_checkbox = QCheckBox("Enable web search by default")
        search_checkbox.setChecked(search_enabled)
        layout.addWidget(search_checkbox)

        # Search URL
        layout.addWidget(QLabel("Search Engine URL (SearXNG):"))
        search_url_input = QLineEdit(self.settings.get("search_url", ""))
        search_url_input.setPlaceholderText("http://localhost:8080/search")
        layout.addWidget(search_url_input)

        # Buttons
        button_layout = QHBoxLayout()

        def save_settings():
            self.settings["vllm_endpoint_url"] = endpoint_input.text()
            self.settings["model_name"] = model_input.text()
            self.settings["api_key"] = api_input.text()
            self.settings["search_enabled"] = search_checkbox.isChecked()
            self.settings["search_url"] = search_url_input.text()
            self.save_settings(self.settings)

            # Reinitialize pipeline with new settings
            self.pipeline = Pipeline(
                endpoint_url=self.settings.get(
                    "vllm_endpoint_url", "http://localhost:8000/v1"
                ),
                model_name=self.settings.get("model_name", "default"),
                api_key=self.settings.get("api_key", "empty"),
            )

            # Update search URL in search module
            global DEFAULT_SEARXNG_URL
            from search import DEFAULT_SEARXNG_URL
            import search

            search.DEFAULT_SEARXNG_URL = self.settings.get(
                "search_url", "http://localhost:8080/search"
            )

            QMessageBox.information(
                dialog, "Success", "Settings saved and pipeline reinitialized"
            )
            dialog.accept()

        save_btn = QPushButton("Save")
        save_btn.clicked.connect(save_settings)
        button_layout.addWidget(save_btn)

        # Error log button
        view_errors_btn = QPushButton("View Error Log")
        view_errors_btn.clicked.connect(self.view_error_log)
        button_layout.addWidget(view_errors_btn)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.clicked.connect(dialog.reject)
        button_layout.addWidget(cancel_btn)

        button_layout.addStretch()
        layout.addLayout(button_layout)

        dialog.exec()

    def view_error_log(self):
        """Open error log viewer"""
        from error_tracker import error_tracker

        dialog = QDialog(self)
        dialog.setWindowTitle("Error Log")
        dialog.setGeometry(200, 200, 800, 600)

        layout = QVBoxLayout(dialog)

        # Summary
        summary = error_tracker.get_error_summary()
        summary_text = "<b>Error Summary:</b><br>"
        for error_type, data in summary.items():
            summary_text += f"{error_type}: {data['count']} error(s)<br>"

        if not summary:
            summary_text = "<b>No errors logged</b>"

        summary_label = QLabel(summary_text)
        summary_label.setWordWrap(True)
        summary_label.setStyleSheet(
            "background-color: #2a2a2a; padding: 10px; border-radius: 4px;"
        )
        layout.addWidget(summary_label)

        # Error details
        error_text = QTextEdit()
        error_text.setReadOnly(True)
        error_text.setStyleSheet("""
            QTextEdit {
                background-color: #0a0a0a;
                color: #00ff00;
                font-family: Consolas;
                font-size: 10px;
                padding: 10px;
            }
        """)

        for error in error_tracker.get_errors():
            error_text.append(f"<b>{error['timestamp']}</b>")
            error_text.append(f"<b>Type:</b> {error['type']}")
            error_text.append(f"<b>Message:</b> {error['message']}")
            if error.get("context"):
                error_text.append(
                    f"<b>Context:</b> {json.dumps(error['context'], indent=2, default=str)}"
                )
            error_text.append("<hr>")

        layout.addWidget(error_text)

        # Clear button
        clear_btn = QPushButton("Clear Error Log")
        clear_btn.clicked.connect(lambda: self.clear_error_log(error_tracker, dialog))
        layout.addWidget(clear_btn)

        dialog.exec()

    def clear_error_log(self, tracker, dialog):
        """Clear error log"""
        tracker.errors = []
        QMessageBox.information(dialog, "Success", "Error log cleared")
        dialog.accept()

    def handle_chat_anchor_click(self, url):
        """Handle clicks on links in chat - supports tts: scheme for TTS"""
        url_str = url.toString()

        if url_str.startswith("tts:"):
            # Extract message ID
            message_id = url_str[4:]  # Remove "tts:" prefix

            # Get the message text
            if hasattr(self, "_tts_messages") and message_id in self._tts_messages:
                text = self._tts_messages[message_id]

                # Stop any currently playing TTS
                from tts_client import get_tts_client

                tts_client = get_tts_client()
                tts_client.stop()

                # Play TTS for this message
                if len(text) < 50:
                    QMessageBox.warning(self, "Warning", "Message is too short for TTS")
                    return

                # Update UI - disable chat TTS controls
                self.tts_play_report_btn.setEnabled(False)
                self.tts_stop_report_btn.setEnabled(True)
                self.tts_status_label.setText("Generating...")
                self.tts_report_voice_combo.setEnabled(False)

                # Get voice from combo box
                voice = self.tts_report_voice_combo.currentText()

                # Start generation and playback with file saving
                tts_client.generate_and_play(
                    text,
                    voice=voice,
                    save_to_file=True,
                    progress_callback=lambda msg: self.tts_status_label.setText(msg),
                    complete_callback=lambda error=None: self.on_tts_finished(error),
                )
            else:
                QMessageBox.warning(self, "Warning", "Message not found for TTS")
        else:
            # Handle other links normally
            QMessageBox.information(self, "Link Clicked", f"Link: {url_str}")

    # ========== TTS Methods ==========

    def toggle_play_pause(self):
        """Toggle between play and pause (legacy - kept for compatibility)"""
        self.play_report_tts()

    def play_report_tts(self):
        """Play the full report using Kokoro PyTorch TTS with CUDA GPU"""
        if not self.current_report:
            QMessageBox.warning(self, "Warning", "No report to read")
            return

        # Extract text from report
        text = self.extract_report_text()

        if len(text) < 50:
            QMessageBox.warning(self, "Warning", "Report is too short for TTS")
            return

        # Update UI
        self.tts_play_report_btn.setEnabled(False)
        self.tts_stop_report_btn.setEnabled(True)
        self.tts_status_label.setText("Generating...")
        self.tts_report_voice_combo.setEnabled(False)

        # Start generation and playback with file saving
        voice = self.tts_report_voice_combo.currentText()
        client = get_tts_client()
        client.generate_and_play(
            text,
            voice=voice,
            save_to_file=True,
            progress_callback=lambda msg: self.tts_status_label.setText(msg),
            complete_callback=lambda error=None: self.on_tts_finished(),
        )

    def on_tts_finished(self, error=None):
        """Handle TTS completion"""
        if error:
            QMessageBox.warning(self, "Warning", f"Playback failed: {error}")
            self.tts_status_label.setText("Error")
        else:
            self.tts_status_label.setText("Complete")

        self.tts_play_report_btn.setEnabled(True)
        self.tts_stop_report_btn.setEnabled(False)
        self.tts_report_voice_combo.setEnabled(True)

    def stop_tts(self):
        """Stop TTS playback"""
        try:
            client = get_tts_client()
            client.stop()
            self.tts_status_label.setText("Stopped")
            self.tts_play_report_btn.setEnabled(True)
            self.tts_stop_report_btn.setEnabled(False)
            self.tts_report_voice_combo.setEnabled(True)
            self.statusBar().showMessage("Playback stopped", 2000)
        except Exception as e:
            QMessageBox.warning(self, "Warning", f"Could not stop: {str(e)}")

    def extract_report_text(self) -> str:
        """Extract plain text from markdown report for TTS"""
        import re

        text = self.report_content.toPlainText()

        # Remove markdown formatting
        text = re.sub(r"#\s+", "", text)  # Headers
        text = re.sub(r"\*\*(.+?)\*\*", r"\1", text)  # Bold
        text = re.sub(r"\*(.+?)\*", r"\1", text)  # Italic
        text = re.sub(r"-\s+", "", text)  # Bullet points
        text = re.sub(r"\n{3,}", "\n\n", text)  # Multiple newlines

        return text.strip()

    def on_tts_error(self, error_tuple):
        """Handle TTS errors"""
        error_msg, title = error_tuple
        QMessageBox.critical(self, title, str(error_msg))

        # Reset UI
        self.tts_play_report_btn.setEnabled(True)
        self.tts_stop_report_btn.setEnabled(False)
        self.tts_report_voice_combo.setEnabled(True)
        self.tts_status_label.setText("Error")


def main():
    """Main entry point"""
    app = QApplication(sys.argv)
    app.setApplicationName("Deliberate AI")

    # Apply global stylesheet
    app.setStyleSheet("""
        QMainWindow {
            background-color: #1a1a1a;
        }
        QGroupBox {
            font-weight: bold;
            border: 1px solid #444;
            border-radius: 4px;
            margin-top: 10px;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 5px;
        }
    """)

    window = DeliberateAI()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
