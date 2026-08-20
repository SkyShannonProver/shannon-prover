"""Terminal status/colors for orchestrator runs.

Extracted verbatim from the retired progress facade (backlog #18): the color
vocabulary, timestamped status() line, the single-line status bar, and the
phase print helpers (phase_start/phase_done/error).
"""
from __future__ import annotations

import sys
from datetime import datetime


_BOLD = "\033[1m"


_DIM = "\033[2m"


_GREEN = "\033[32m"


_YELLOW = "\033[33m"


_CYAN = "\033[36m"


_RED = "\033[31m"


_RESET = "\033[0m"


def _timestamp() -> str:
    return datetime.now().strftime("%H:%M:%S")


_status_bar_text = ""  # current status bar content


_status_bar_active = False  # whether the status bar is being shown


def _clear_status_bar():
    """Clear the status bar line (if active) before printing a log line."""
    if _status_bar_active and _status_bar_text:
        # Move to start of line, clear it
        sys.stdout.write(f"\r\033[2K")
        sys.stdout.flush()


def _draw_status_bar():
    """Redraw the status bar at the bottom after a log line is printed."""
    if _status_bar_active and _status_bar_text:
        sys.stdout.write(f"\r{_DIM}{_status_bar_text}{_RESET}")
        sys.stdout.flush()


def _update_status_bar(text: str):
    """Update the status bar content. Called by prover monitoring loop."""
    global _status_bar_text
    _status_bar_text = text
    if _status_bar_active:
        sys.stdout.write(f"\r\033[2K{_DIM}{_status_bar_text}{_RESET}")
        sys.stdout.flush()


def _set_status_bar_active(active: bool):
    """Enable/disable the status bar."""
    global _status_bar_active
    if not active and _status_bar_active:
        # Clear the bar when deactivating
        sys.stdout.write(f"\r\033[2K")
        sys.stdout.flush()
    _status_bar_active = active


def status(agent: str, message: str, color: str = _CYAN) -> None:
    """Print a timestamped status line."""
    _clear_status_bar()
    print(f"{_DIM}{_timestamp()}{_RESET} {color}{_BOLD}[{agent}]{_RESET} {message}")
    sys.stdout.flush()
    _draw_status_bar()


def phase_start(phase: str) -> None:
    """Print a phase header."""
    print(f"\n{_BOLD}{'─' * 50}{_RESET}")
    print(f"{_DIM}{_timestamp()}{_RESET} {_YELLOW}{_BOLD}▶ {phase}{_RESET}")
    print(f"{_BOLD}{'─' * 50}{_RESET}")
    sys.stdout.flush()


def phase_done(phase: str, result: str = "") -> None:
    """Print phase completion."""
    suffix = f" → {result}" if result else ""
    print(f"{_DIM}{_timestamp()}{_RESET} {_GREEN}{_BOLD}✓ {phase}{suffix}{_RESET}\n")
    sys.stdout.flush()


def error(agent: str, message: str) -> None:
    """Print an error."""
    print(f"{_DIM}{_timestamp()}{_RESET} {_RED}{_BOLD}✗ [{agent}]{_RESET} {_RED}{message}{_RESET}")
    sys.stdout.flush()
