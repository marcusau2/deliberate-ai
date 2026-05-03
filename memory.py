"""
SQLite-backed persistent memory for Deliberate AI debate system.

Stores persona state, responses, position history, and influence tracking
to enable genuine multi-round debate with full context awareness.
"""

import sqlite3
import json
import logging
from pathlib import Path
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)

# Database storage
DB_DIR = Path("debate_data")
DB_DIR.mkdir(exist_ok=True)


def _get_db_path(session_id: str) -> Path:
    """Get database path for a debate session."""
    return DB_DIR / f"debate_{session_id}.db"


def _get_connection(session_id: str) -> sqlite3.Connection:
    """Get a database connection for a session."""
    db_path = _get_db_path(session_id)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_session(session_id: str) -> str:
    """Initialize a new debate session database.

    Returns the session_id for tracking.
    """
    conn = _get_connection(session_id)
    cursor = conn.cursor()

    cursor.executescript("""
        CREATE TABLE IF NOT EXISTS personas (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            role_title TEXT,
            organization TEXT,
            approach TEXT,
            background TEXT,
            worldview TEXT,
            likely_bias TEXT,
            initial_position TEXT,
            diversity_role TEXT,
            epistemic_type TEXT,
            option_alignment TEXT
        );

        CREATE TABLE IF NOT EXISTS responses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            persona_id TEXT NOT NULL,
            round_num INTEGER NOT NULL,
            position TEXT,
            reaction TEXT,
            shift TEXT DEFAULT 'none',
            influenced_by TEXT,
            full_context TEXT,
            timestamp TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (persona_id) REFERENCES personas(id)
        );

        CREATE TABLE IF NOT EXISTS positions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            persona_id TEXT NOT NULL,
            round_num INTEGER NOT NULL,
            stance TEXT,
            stance_vector TEXT,
            confidence REAL DEFAULT 50.0,
            option_preference TEXT,
            key_arguments TEXT,
            FOREIGN KEY (persona_id) REFERENCES personas(id)
        );

        CREATE TABLE IF NOT EXISTS influence (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            influencer_id TEXT NOT NULL,
            influenced_id TEXT NOT NULL,
            round_num INTEGER NOT NULL,
            argument_summary TEXT,
            shift_magnitude TEXT DEFAULT 'none',
            FOREIGN KEY (influencer_id) REFERENCES personas(id),
            FOREIGN KEY (influenced_id) REFERENCES personas(id)
        );

        CREATE TABLE IF NOT EXISTS decision_context (
            key TEXT PRIMARY KEY,
            value TEXT
        );

        CREATE INDEX IF NOT EXISTS idx_responses_persona ON responses(persona_id, round_num);
        CREATE INDEX IF NOT EXISTS idx_positions_persona ON positions(persona_id, round_num);
        CREATE INDEX IF NOT EXISTS idx_influence_round ON influence(round_num);
    """)

    conn.commit()
    conn.close()
    logger.info(f"Initialized debate session: {session_id}")
    return session_id


def cleanup_session(session_id: str):
    """Remove a debate session database."""
    db_path = _get_db_path(session_id)
    if db_path.exists():
        db_path.unlink()
        logger.info(f"Cleaned up debate session: {session_id}")


def store_decision_context(session_id: str, decision_data: dict):
    """Store the decision structure extracted from user input.

    decision_data should contain:
        question_type: binary | multi_option | open_ended | analysis
        options: list of options (for multi_option/open_ended)
        evaluation_criteria: list of criteria
        core_issue: string
        original_input: string
    """
    conn = _get_connection(session_id)
    for key, value in decision_data.items():
        if isinstance(value, (list, dict)):
            value = json.dumps(value)
        conn.execute(
            "INSERT OR REPLACE INTO decision_context (key, value) VALUES (?, ?)",
            (key, str(value)),
        )
    conn.commit()
    conn.close()


def get_decision_context(session_id: str) -> dict:
    """Retrieve the decision structure."""
    conn = _get_connection(session_id)
    rows = conn.execute("SELECT key, value FROM decision_context").fetchall()
    conn.close()

    result = {}
    for row in rows:
        value = row["value"]
        # Try to parse JSON for lists/dicts
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            pass
        result[row["key"]] = value
    return result


def store_persona(session_id: str, persona: dict):
    """Store a persona's full profile."""
    conn = _get_connection(session_id)
    conn.execute(
        """INSERT OR REPLACE INTO personas
           (id, name, role_title, organization, approach, background,
            worldview, likely_bias, initial_position, diversity_role,
            epistemic_type, option_alignment)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            persona.get("id", ""),
            persona.get("name", ""),
            persona.get("role_title", ""),
            persona.get("organization", ""),
            persona.get("approach", ""),
            persona.get("background", ""),
            persona.get("worldview", ""),
            persona.get("likely_bias", ""),
            persona.get("initial_position", ""),
            persona.get("diversity_role", ""),
            persona.get("epistemic_type", ""),
            json.dumps(persona.get("option_alignment", [])),
        ),
    )
    conn.commit()
    conn.close()


def get_all_personas(session_id: str) -> list:
    """Retrieve all personas."""
    conn = _get_connection(session_id)
    rows = conn.execute("SELECT * FROM personas").fetchall()
    conn.close()

    personas = []
    for row in rows:
        persona = dict(row)
        # Parse option_alignment from JSON
        if persona.get("option_alignment"):
            try:
                persona["option_alignment"] = json.loads(persona["option_alignment"])
            except json.JSONDecodeError:
                persona["option_alignment"] = []
        personas.append(persona)
    return personas


def store_response(session_id: str, persona_id: str, round_num: int, response: dict):
    """Store a persona's response for a given round."""
    conn = _get_connection(session_id)
    conn.execute(
        """INSERT INTO responses
           (persona_id, round_num, position, reaction, shift, influenced_by, full_context)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            persona_id,
            round_num,
            response.get("position", ""),
            response.get("reaction", ""),
            response.get("shift", "none"),
            json.dumps(response.get("influenced_by", [])),
            json.dumps(response),
        ),
    )
    conn.commit()
    conn.close()


def get_persona_history(session_id: str, persona_id: str) -> list:
    """Get all responses for a specific persona, ordered by round.

    Used to build the persona's own memory of what they've said.
    """
    conn = _get_connection(session_id)
    rows = conn.execute(
        """SELECT round_num, position, reaction, shift, influenced_by
           FROM responses
           WHERE persona_id = ?
           ORDER BY round_num ASC""",
        (persona_id,),
    ).fetchall()
    conn.close()

    return [dict(row) for row in rows]


def get_current_round_responses(session_id: str, round_num: int, exclude_persona: str = None) -> list:
    """Get all responses for a specific round, optionally excluding one persona.

    Used so a persona can see what others have said in the current round.
    """
    conn = _get_connection(session_id)
    if exclude_persona:
        rows = conn.execute(
            """SELECT r.*, p.name, p.approach
               FROM responses r
               JOIN personas p ON r.persona_id = p.id
               WHERE r.round_num = ? AND r.persona_id != ?
               ORDER BY r.id ASC""",
            (round_num, exclude_persona),
        ).fetchall()
    else:
        rows = conn.execute(
            """SELECT r.*, p.name, p.approach
               FROM responses r
               JOIN personas p ON r.persona_id = p.id
               WHERE r.round_num = ?
               ORDER BY r.id ASC""",
            (round_num,),
        ).fetchall()
    conn.close()

    results = []
    for row in rows:
        result = dict(row)
        if result.get("influenced_by"):
            try:
                result["influenced_by"] = json.loads(result["influenced_by"])
            except json.JSONDecodeError:
                result["influenced_by"] = []
        results.append(result)
    return results


def get_relevant_counterarguments(session_id: str, persona_id: str, current_round: int) -> list:
    """Find responses that directly challenge this persona's position.

    Queries previous rounds for responses where this persona was listed
    as influenced, or where the response indicates a shift (suggesting
    the persona's position was challenged).
    """
    conn = _get_connection(session_id)

    # Find rounds where this persona was influenced by others
    rows = conn.execute(
        """SELECT r.*, p.name, p.approach
           FROM responses r
           JOIN personas p ON r.persona_id = p.id
           WHERE r.round_num < ?
             AND r.persona_id != ?
             AND r.shift != 'none'
           ORDER BY r.round_num DESC
           LIMIT 5""",
        (current_round, persona_id),
    ).fetchall()

    conn.close()
    return [dict(row) for row in rows]


def store_position(session_id: str, persona_id: str, round_num: int, position_data: dict):
    """Store extracted stance/position data for a persona at a given round.

    position_data should contain:
        stance: support | oppose | compromise | neutral
        stance_vector: dict of dimension scores
        confidence: 0-100
        option_preference: which option they lean toward (for multi-option)
        key_arguments: list of key arguments
    """
    conn = _get_connection(session_id)
    conn.execute(
        """INSERT OR REPLACE INTO positions
           (persona_id, round_num, stance, stance_vector, confidence,
            option_preference, key_arguments)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            persona_id,
            round_num,
            position_data.get("stance", "neutral"),
            json.dumps(position_data.get("stance_vector", {})),
            position_data.get("confidence", 50.0),
            position_data.get("option_preference", ""),
            json.dumps(position_data.get("key_arguments", [])),
        ),
    )
    conn.commit()
    conn.close()


def get_position_trajectory(session_id: str, persona_id: str) -> list:
    """Get the full position trajectory for a persona across all rounds.

    Used for genuine shift detection and report generation.
    """
    conn = _get_connection(session_id)
    rows = conn.execute(
        """SELECT round_num, stance, stance_vector, confidence, option_preference, key_arguments
           FROM positions
           WHERE persona_id = ?
           ORDER BY round_num ASC""",
        (persona_id,),
    ).fetchall()
    conn.close()

    results = []
    for row in rows:
        result = dict(row)
        for field in ["stance_vector", "key_arguments"]:
            if result.get(field):
                try:
                    result[field] = json.loads(result[field])
                except json.JSONDecodeError:
                    result[field] = {}
        results.append(result)
    return results


def store_influence(session_id: str, influencer_id: str, influenced_id: str,
                    round_num: int, argument_summary: str, shift_magnitude: str = "none"):
    """Record that one persona influenced another."""
    conn = _get_connection(session_id)
    conn.execute(
        """INSERT INTO influence
           (influencer_id, influenced_id, round_num, argument_summary, shift_magnitude)
           VALUES (?, ?, ?, ?, ?)""",
        (influencer_id, influenced_id, round_num, argument_summary, shift_magnitude),
    )
    conn.commit()
    conn.close()


def get_influence_graph(session_id: str) -> list:
    """Get the full influence graph across all rounds."""
    conn = _get_connection(session_id)
    rows = conn.execute("""
        SELECT i.*,
               p1.name as influencer_name,
               p2.name as influenced_name
        FROM influence i
        JOIN personas p1 ON i.influencer_id = p1.id
        JOIN personas p2 ON i.influenced_id = p2.id
        ORDER BY i.round_num ASC
    """).fetchall()
    conn.close()
    return [dict(row) for row in rows]


def get_option_convergence(session_id: str, round_num: int) -> dict:
    """Get how personas are distributed across options at a given round.

    Returns dict: {option_name: [persona_ids aligned with this option]}
    """
    context = get_decision_context(session_id)
    options = context.get("options", [])
    if not options:
        return {}

    conn = _get_connection(session_id)
    rows = conn.execute(
        """SELECT persona_id, option_preference
           FROM positions
           WHERE round_num = ?
           ORDER BY persona_id""",
        (round_num,),
    ).fetchall()
    conn.close()

    convergence = {opt: [] for opt in options}
    convergence["undecided"] = []

    for row in rows:
        pref = row["option_preference"] or "undecided"
        if pref in convergence:
            convergence[pref].append(row["persona_id"])
        else:
            convergence["undecided"].append(row["persona_id"])

    return convergence


def build_debate_context(session_id: str, persona_id: str, current_round: int) -> dict:
    """Build targeted debate context for a persona.

    Returns a dict with:
        own_history: What this persona has said in previous rounds
        current_round_responses: What others have said this round
        counterarguments: Previous responses that challenged this persona
        decision_context: The decision structure
        option_convergence: How options are tracking (if multi-option)
    """
    own_history = get_persona_history(session_id, persona_id)
    current_round = get_current_round_responses(session_id, current_round, exclude_persona=persona_id)
    counterarguments = get_relevant_counterarguments(session_id, persona_id, current_round)
    decision_context = get_decision_context(session_id)

    result = {
        "own_history": own_history,
        "current_round_responses": current_round,
        "counterarguments": counterarguments,
        "decision_context": decision_context,
    }

    # Add option convergence for multi-option questions
    options = decision_context.get("options", [])
    if options:
        result["option_convergence"] = get_option_convergence(session_id, current_round - 1)

    return result
