#!/usr/bin/env python3
"""
Nyx Memory Utilities - Shared Functions

Common functions used across:
- actr_ranker.py
- visualize.py  
- nyx_tui.py

This module consolidates duplicate code from all three files.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ============================================================================
# CONFIGURATION
# ============================================================================

MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", "/home/node/.openclaw/workspace"))
MEMORY_BASE_DIR = Path(os.environ.get("MEMORY_BASE_DIR", "/home/node/.openclaw"))

ACTIVATION_LOG = MEMORY_BASE_DIR / "memory/activation-log.json"
TAG_GRAPH_PATH = MEMORY_BASE_DIR / "memory/tag-graph.json"
PAGERANK_SCORES_PATH = MEMORY_BASE_DIR / "memory/pagerank-scores.json"

# ============================================================================
# ANSI COLORS
# ============================================================================

RESET = "\033[0m"
BOLD = "\033[1m"

GREEN = "\033[92m"
YELLOW = "\033[93m"
RED = "\033[91m"
BLUE = "\033[94m"
CYAN = "\033[96m"
GRAY = "\033[90m"


def colorize(text, color):
    """Apply ANSI color to text."""
    return f"{color}{text}{RESET}"


def success(text):
    """Green text for success messages."""
    return colorize(text, GREEN)


def warning(text):
    """Yellow text for warnings."""
    return colorize(text, YELLOW)


def error(text):
    """Red text for errors."""
    return colorize(text, RED)


def header(text):
    """Blue bold text for headers."""
    return colorize(f"{BOLD}{text}", BLUE)


def highlight(text):
    """Cyan text for highlights."""
    return colorize(text, CYAN)


def muted(text):
    """Gray text for muted info."""
    return colorize(text, GRAY)


# ============================================================================
# ACT-R CONFIGURATION
# ============================================================================

BASE_LEVEL = 0.3
DECAY_CONSTANT = 0.5


# ============================================================================
# DATA LOADING FUNCTIONS
# ============================================================================

# In-memory caches
_activation_cache = None
_tag_graph_cache = None
_pagerank_cache = None


def load_activation_log(force_reload=False):
    """
    Load the activation log with caching.
    
    Args:
        force_reload: If True, bypass cache and reload from disk
        
    Returns:
        dict: Activation log data
    """
    global _activation_cache
    
    if _activation_cache is not None and not force_reload:
        return _activation_cache
    
    try:
        if ACTIVATION_LOG.exists():
            with open(ACTIVATION_LOG) as f:
                _activation_cache = json.load(f)
                return _activation_cache
    except Exception:
        pass
    
    _activation_cache = {"version": "1.0", "last_updated": None, "items": {}}
    return _activation_cache


def save_activation_log(data):
    """
    Save the activation log.
    
    Args:
        data: Activation log dict to save
    """
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(ACTIVATION_LOG, "w") as f:
        json.dump(data, f, indent=2)
    
    global _activation_cache
    _activation_cache = data


def load_tag_graph(force_reload=False):
    """
    Load the tag graph with caching.
    
    Args:
        force_reload: If True, bypass cache and reload from disk
        
    Returns:
        dict: Tag graph data
    """
    global _tag_graph_cache
    
    if _tag_graph_cache is not None and not force_reload:
        return _tag_graph_cache
    
    if TAG_GRAPH_PATH.exists():
        try:
            with open(TAG_GRAPH_PATH) as f:
                _tag_graph_cache = json.load(f)
                return _tag_graph_cache
        except Exception:
            pass
    
    _tag_graph_cache = {"nodes": {}, "edges": [], "tag_index": {}}
    return _tag_graph_cache


def load_pagerank_scores(force_reload=False):
    """
    Load PageRank scores with caching.
    
    Args:
        force_reload: If True, bypass cache and reload from disk
        
    Returns:
        dict: PageRank scores {slug: score}
    """
    global _pagerank_cache
    
    if _pagerank_cache is not None and not force_reload:
        return _pagerank_cache
    
    try:
        if PAGERANK_SCORES_PATH.exists():
            with open(PAGERANK_SCORES_PATH) as f:
                data = json.load(f)
                _pagerank_cache = data.get("scores", {})
                return _pagerank_cache
    except Exception:
        pass
    
    _pagerank_cache = {}
    return _pagerank_cache


def load_tags_from_file(path):
    """
    Load tags from a problem markdown file.
    
    Args:
        path: Relative path to the problem file
        
    Returns:
        list: List of tag strings
    """
    full_path = MEMORY_DIR / path
    if not full_path.exists():
        return []
    
    try:
        content = full_path.read_text()
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('**Tags:**'):
                tags_str = line.replace('**Tags:**', '').strip()
                if tags_str:
                    return [t.strip().rstrip(',') for t in tags_str.split() if t.strip()]
    except Exception:
        pass
    
    return []


def get_status_from_file(path):
    """
    Get status from a problem markdown file.
    
    Args:
        path: Relative path to the problem file
        
    Returns:
        str: Status string ('open', 'in-progress', 'resolved', 'dead-end', or 'unknown')
    """
    full_path = MEMORY_DIR / path
    if not full_path.exists():
        return "unknown"
    
    try:
        content = full_path.read_text()
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('**Status:**'):
                status = line.replace('**Status:**', '').strip().lower()
                # Normalize status values
                if status in ['open', 'in-progress', 'in_progress', 'resolved', 'dead-end', 'dead_end']:
                    return status.replace('_', '-')
                return status
    except Exception:
        pass
    
    return "unknown"


# ============================================================================
# ACTIVATION CALCULATION
# ============================================================================

def calculate_activation(item_data, current_time):
    """
    Calculate ACT-R style activation.
    
    A = B + Σ(Sᵢ / Dᵢ) - F
    
    Args:
        item_data: Problem item from activation log
        current_time: Current datetime
        
    Returns:
        float: Activation score (0-1, clamped)
    """
    access_times = item_data.get("access_times", [])
    if not access_times:
        return BASE_LEVEL
    
    try:
        # Calculate recency (most recent access)
        last_access = datetime.fromisoformat(access_times[-1].replace("Z", "+00:00"))
        seconds_ago = (current_time - last_access).total_seconds()
        recency = 1.0 / ((seconds_ago / 3600) + 1)
        
        # Frequency bonus
        frequency = len(access_times)
        frequency_bonus = 0.1 * (frequency - 1)
        
        # Age decay
        age = (current_time - datetime.fromisoformat(
            item_data["created"].replace("Z", "+00:00")
        )).total_seconds() / 86400
        
        decay = DECAY_CONSTANT * (age ** 0.5)
        
        activation = BASE_LEVEL + recency * 0.4 + frequency_bonus - decay
        return max(0.0, min(1.0, activation))
    except Exception:
        return BASE_LEVEL


def clear_caches():
    """Clear all in-memory caches (for testing)."""
    global _activation_cache, _tag_graph_cache, _pagerank_cache
    _activation_cache = None
    _tag_graph_cache = None
    _pagerank_cache = None
