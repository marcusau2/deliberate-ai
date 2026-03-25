"""
Error tracking and logging module for Deliberate AI
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path

# Create logs directory
LOGS_DIR = Path("logs")
LOGS_DIR.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler(
            LOGS_DIR / f"error_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
        ),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)


class ErrorTracker:
    """Track and log errors with context"""

    def __init__(self):
        self.errors = []
        self.error_file = LOGS_DIR / f"errors_{datetime.now().strftime('%Y%m%d')}.json"

    def log_error(self, error_type: str, message: str, context: dict = None):
        """Log an error with full context"""
        error_data = {
            "timestamp": datetime.now().isoformat(),
            "type": error_type,
            "message": message,
            "context": context or {},
        }

        self.errors.append(error_data)
        logger.error(f"[{error_type}] {message}")

        if context:
            logger.debug(f"Context: {json.dumps(context, indent=2, default=str)}")

        # Save to file
        self._save_errors()

        return error_data

    def _save_errors(self):
        """Save errors to JSON file"""
        try:
            with open(self.error_file, "w") as f:
                json.dump(self.errors, f, indent=2, default=str)
        except Exception as e:
            logger.error(f"Failed to save errors: {e}")

    def get_errors(self):
        """Get all logged errors"""
        return self.errors

    def get_error_summary(self):
        """Get summary of errors by type"""
        summary = {}
        for error in self.errors:
            error_type = error["type"]
            if error_type not in summary:
                summary[error_type] = {"count": 0, "messages": set()}
            summary[error_type]["count"] += 1
            summary[error_type]["messages"].add(error["message"])

        # Convert sets to lists for JSON serialization
        for error_type in summary:
            summary[error_type]["messages"] = list(summary[error_type]["messages"])

        return summary


# Global error tracker instance
error_tracker = ErrorTracker()


def log_pipeline_error(stage: str, error: Exception, context: dict = None):
    """Log pipeline errors with stage context"""
    error_tracker.log_error(
        error_type=f"Pipeline_{stage}", message=str(error), context=context
    )


def log_ui_error(widget: str, error: Exception, context: dict = None):
    """Log UI errors with widget context"""
    error_tracker.log_error(
        error_type=f"UI_{widget}", message=str(error), context=context
    )
