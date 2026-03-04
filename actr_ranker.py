#!/usr/bin/env python3
"""
ACT-R Style Activation Ranker

Unified gateway combining:
- QMD semantic search
- ACT-R activation (recency + frequency)
- PageRank (tag graph centrality)
- Explicit relationships

Formula: Final = 0.50×QMD + 0.15×Activation + 0.25×PageRank + 0.10×Relationships
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import yaml

# Import shared utilities
from memory_utils import (
    load_activation_log as _utils_load_activation_log,
    save_activation_log as _utils_save_activation_log,
    load_tag_graph,
    load_pagerank_scores,
    load_tags_from_file,
    calculate_activation as _utils_calculate_activation,
    BASE_LEVEL,
    DECAY_CONSTANT,
)

# Configure logging
def setup_logging(debug: bool = False, quiet: bool = False):
    """Configure logging based on debug/quiet flags."""
    level = logging.DEBUG if debug else (logging.WARNING if quiet else logging.INFO)
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger(__name__)

logger = logging.getLogger(__name__)

# Try to import SQLite backend
try:
    from db import (
        get_problem, get_all_problems, search_problems,
        record_access as db_record_access, get_stats,
        is_sqlite_available
    )
    SQLITE_AVAILABLE = is_sqlite_available()
except ImportError:
    SQLITE_AVAILABLE = False
    logger.warning("SQLite backend not available, using JSON only")

MEMORY_DIR = Path("/home/node/.openclaw/workspace/memory")
MEMORY_BASE_DIR = Path("/home/node/.openclaw")
ACTIVATION_LOG = MEMORY_BASE_DIR / "memory/activation-log.json"
TAG_GRAPH_PATH = MEMORY_BASE_DIR / "memory/tag-graph.json"
PAGERANK_SCORES_PATH = MEMORY_BASE_DIR / "memory/pagerank-scores.json"
CONFIG_PATH = Path(__file__).parent / "config.yaml"
SQLITE_DB = MEMORY_BASE_DIR / "memory/nyx.db"

# Base directory for safe file operations
SAFE_BASE_DIR = Path("/home/node/.openclaw/workspace")


def validate_path(path):
    """
    Validate a path to prevent directory traversal attacks.
    
    Security checks:
    - No directory traversal (../etc/passwd)
    - Only allows safe characters: alphanumeric, /, -, _, .
    - Must resolve to a path within SAFE_BASE_DIR
    
    Args:
        path: The path string to validate
        
    Returns:
        bool: True if path is safe, False otherwise
    """
    if not path:
        return False
    
    # Check for directory traversal attempts
    if ".." in path or path.startswith("/") or "\\" in path:
        return False
    
    # Only allow safe characters (alphanumeric, hyphen, underscore, dot, forward slash)
    if not re.match(r'^[\w\-./]+$', path):
        return False
    
    try:
        # Resolve the full path and verify it's within SAFE_BASE_DIR
        full_path = (SAFE_BASE_DIR / path).resolve()
        
        # Ensure the resolved path is within SAFE_BASE_DIR
        if not str(full_path).startswith(str(SAFE_BASE_DIR.resolve())):
            return False
        
        return True
    except Exception:
        return False


def load_config():
    """Load configuration from config.yaml."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {}


# Load config
_config = load_config()

# In-memory cache for activation log
activation_cache = None

# Query result cache (for 5-20x speedup on repeated queries)
QUERY_CACHE_TTL = 300  # 5 minutes
query_cache = {}  # {normalized_query: {"results": [...], "timestamp": time}}


def normalize_query(query):
    """Normalize query string for cache key."""
    if not query:
        return ""
    # Lowercase, trim, collapse spaces
    return ' '.join(query.lower().strip().split())


def get_cached_results(query: str) -> Optional[List[Dict[str, Any]]]:
    """Get cached QMD results if not expired."""
    if not query:
        return None
    
    normalized = normalize_query(query)
    
    if normalized not in query_cache:
        return None
    
    entry = query_cache[normalized]
    age = time.time() - entry["timestamp"]
    
    if age > QUERY_CACHE_TTL:
        del query_cache[normalized]
        return None
    
    return entry["results"]


def set_cached_results(query: str, results: List[Dict[str, Any]]) -> None:
    """Cache QMD search results."""
    if not query or not results:
        return
    
    normalized = normalize_query(query)
    query_cache[normalized] = {
        "results": results,
        "timestamp": time.time()
    }


def clear_cache():
    """Clear all in-memory caches (for testing)."""
    global activation_cache
    activation_cache = None
    query_cache.clear()
    logger.info("Query cache cleared.")


# ============================================================================
# IMPROVEMENT 1: PRE-RETRIEVAL CHECK
# ============================================================================

def should_retrieve_memory(query):
    """
    Decide if we need to search memory for this query.
    
    Uses a simple heuristic: if query contains problem/solution/task keywords,
    it's likely the user is asking about something we might have documented.
    
    Args:
        query: The user's search query string
        
    Returns:
        bool: True if memory retrieval is likely useful, False otherwise
    """
    if not query or len(query.strip()) < RETRIEVE_MIN_LENGTH:
        return False
    
    query_lower = query.lower()
    
    # Check if query contains any retrieval-triggering keywords
    for keyword in RETRIEVE_KEYWORDS:
        if keyword in query_lower:
            return True
    
    # Also return True for exact slug matches (user might be asking about a specific problem)
    # This handles cases like "what about the oauth bug?" where no keyword is present
    data = load_activation_log()
    for slug in data.get("items", {}).keys():
        if slug.replace("-", " ") in query_lower or slug.replace("_", " ") in query_lower:
            return True
    
    return False


def get_retrieval_tier(query, force_deep=False):
    """
    Determine which retrieval tier to use for a query.
    
    Tiers:
        - 'fast': Just QMD semantic search (no activation/rank computation)
        - 'deep': Full unified search (QMD + Activation + PageRank + Relationships)
    
    Args:
        query: The search query
        force_deep: If True, always use deep search
        
    Returns:
        str: 'fast' or 'deep'
    """
    # Short/simple queries get fast tier
    if not force_deep and len(query.split()) <= 2:
        return 'fast'
    
    # Complex queries get deep tier
    return 'deep'


# ============================================================================
# IMPROVEMENT 2: MEMORY FRESHNESS & AGING
# ============================================================================

def get_problem_status(slug, data=None):
    """
    Get the status of a problem from its markdown file.
    
    Args:
        slug: Problem slug
        data: Optional pre-loaded activation log
        
    Returns:
        str: 'open', 'in-progress', 'resolved', 'dead-end', or 'unknown'
    """
    if data is None:
        data = load_activation_log()
    
    if slug not in data["items"]:
        return "unknown"
    
    item = data["items"][slug]
    path = item.get("path", f"memory/problems/{slug}.md")
    
    try:
        # Validate path before reading
        if not validate_path(path):
            return "unknown"
        
        full_path = SAFE_BASE_DIR / path
        if not full_path.exists():
            return "unknown"
        
        content = full_path.read_text()
        
        # Look for **Status:** line
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('**Status:**'):
                status = line.replace('**Status:**', '').strip().lower()
                # Normalize status values
                if status in ['open', 'in-progress', 'in_progress', 'resolved', 'dead-end', 'dead_end']:
                    return status.replace('_', '-')
                return "unknown"
    except Exception:
        pass
    
    return "unknown"


def calculate_freshness_decay(item_data, current_time):
    """
    Calculate decay with status-aware aging.
    
    - If problem is "resolved" for >30 days -> reduce activation faster
    - If problem is "dead-end" -> can archive (higher decay)
    
    Args:
        item_data: Problem item from activation log
        current_time: Current datetime
        
    Returns:
        float: Additional decay multiplier based on status and age
    """
    slug = item_data.get("slug", "")
    status = get_problem_status(slug)
    
    if status == "unknown":
        return 1.0  # No extra decay
    
    # Get days since last update
    created = item_data.get("created", "")
    if not created:
        return 1.0
    
    try:
        created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
        days_old = (current_time - created_dt).total_seconds() / 86400
    except Exception:
        return 1.0
    
    # Apply status-based decay multipliers
    if status == "resolved" and days_old > FRESHNESS_RESOLVED_DAYS:
        return FRESHNESS_RESOLVED_DECAY_MULTIPLIER
    elif status == "dead-end" and days_old > FRESHNESS_DEAD_END_DAYS:
        return FRESHNESS_DEAD_END_DECAY_MULTIPLIER
    
    return 1.0  # Normal decay


def apply_freshness_to_all(current_time=None):
    """
    Apply freshness-aware decay to all problems in activation log.
    
    This can be run periodically to update decay rates based on problem status.
    
    Args:
        current_time: Optional datetime, defaults to now
        
    Returns:
        dict: Summary of changes made
    """
    if current_time is None:
        current_time = datetime.now(timezone.utc)
    
    data = load_activation_log()
    
    resolved_decayed = 0
    dead_end_decayed = 0
    archived = 0
    
    for slug, item in data["items"].items():
        status = get_problem_status(slug, data)
        
        if status == "resolved":
            # Check if past threshold
            created = item.get("created", "")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    days_old = (current_time - created_dt).total_seconds() / 86400
                    if days_old > FRESHNESS_RESOLVED_DAYS:
                        # Apply extra decay
                        item["freshness_decay"] = FRESHNESS_RESOLVED_DECAY_MULTIPLIER
                        resolved_decayed += 1
                except Exception:
                    pass
        
        elif status == "dead-end":
            created = item.get("created", "")
            if created:
                try:
                    created_dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
                    days_old = (current_time - created_dt).total_seconds() / 86400
                    if days_old > FRESHNESS_DEAD_END_DAYS:
                        # Mark for archiving
                        item["archival_candidate"] = True
                        archived += 1
                        dead_end_decayed += 1
                except Exception:
                    pass
    
    if resolved_decayed > 0 or dead_end_decayed > 0:
        save_activation_log(data)
    
    return {
        "resolved_decayed": resolved_decayed,
        "dead_end_decayed": dead_end_decayed,
        "archived": archived
    }


# ============================================================================
# IMPROVEMENT 3: FAST/SLOW TIERS
# ============================================================================

def fast_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Fast tier: Just QMD semantic search (no activation/rank computation).
    
    Use for quick, simple queries where speed matters more than precision.
    
    Args:
        query: Search query
        max_results: Maximum results to return
        
    Returns:
        list: Results with just slug, path, and qmd_score
    """
    qmd_results = search_qmd(query, max_results=max_results)
    
    # Return simplified results
    return [
        {
            "slug": r["slug"],
            "path": r["path"],
            "qmd_score": r["qmd_score"]
        }
        for r in qmd_results
    ]


def tiered_search(query, max_results=5, force_deep=False):
    """
    Tiered retrieval: chooses fast or deep based on query complexity.
    
    This is the main entry point that replaces unified_search for most use cases.
    
    Args:
        query: Search query
        max_results: Maximum results to return
        force_deep: If True, always use deep search
        
    Returns:
        dict: {
            "tier": "fast" or "deep",
            "results": [...],
            "retrieval_needed": bool
        }
    """
    # First check if we should retrieve at all
    retrieval_needed = should_retrieve_memory(query)
    
    if not retrieval_needed:
        return {
            "tier": "none",
            "results": [],
            "retrieval_needed": False,
            "reason": "query_not_memory_related"
        }
    
    # Determine tier
    tier = get_retrieval_tier(query, force_deep=force_deep)
    
    if tier == "fast":
        return {
            "tier": "fast",
            "results": fast_search(query, max_results),
            "retrieval_needed": True
        }
    else:
        return {
            "tier": "deep",
            "results": unified_search(query, max_results),
            "retrieval_needed": True
        }

# Weights for unified search (optimized for recall)
# QMD dominates for semantic recall, other signals provide tie-breaking
WEIGHT_QMD = _config.get("weights", {}).get("qmd", 0.50)          # Semantic similarity - primary recall signal
WEIGHT_ACTIVATION = _config.get("weights", {}).get("activation", 0.15)   # Frequency/recency - secondary
WEIGHT_PAGERANK = _config.get("weights", {}).get("pagerank", 0.25)     # Graph importance - tertiary
WEIGHT_RELATIONSHIPS = _config.get("weights", {}).get("relationships", 0.10)  # Explicit links - bonus
EXACT_MATCH_BONUS_DEFAULT = _config.get("weights", {}).get("exact_match_bonus", 0.10)    # Boost for query words in slug

# Formula: Final = 0.50×QMD + 0.15×Activation + 0.25×PageRank + 0.10×Relationships + ExactMatch

# ACT-R Parameters
BASE_LEVEL = _config.get("actr", {}).get("base_level", 0.3)  # B: base-level activation
DECAY_CONSTANT = _config.get("actr", {}).get("decay_constant", 0.5)  # F: forgetting constant
SPREADING_STRENGTH = _config.get("actr", {}).get("spreading_strength", 0.2)  # S: strength of spreading activation

# Freshness/aging parameters
FRESHNESS_RESOLVED_DAYS = _config.get("freshness", {}).get("resolved_days", 30)  # Days after which resolved problems decay faster
FRESHNESS_DEAD_END_DAYS = _config.get("freshness", {}).get("dead_end_days", 60)  # Days after which dead-end problems can be archived
FRESHNESS_RESOLVED_DECAY_MULTIPLIER = _config.get("freshness", {}).get("resolved_decay_multiplier", 2.0)  # Extra decay for resolved problems
FRESHNESS_DEAD_END_DECAY_MULTIPLIER = _config.get("freshness", {}).get("dead_end_decay_multiplier", 3.0)  # Extra decay for dead-end problems

# Pre-retrieval check parameters
RETRIEVE_KEYWORDS = _config.get("pre_retrieval", {}).get("keywords", [
    "problem", "solution", "fix", "error", "bug", "issue", "task", "how", "why",
    "implement", "configure", "setup", "build", "create", "find", "remember",
    "worked", "tried", "before", "previous", "past", "learned", "documented"
])
RETRIEVE_MIN_LENGTH = _config.get("pre_retrieval", {}).get("min_length", 3)  # Minimum query length to consider


def load_activation_log() -> Dict[str, Any]:
    """Load the activation log with SQLite as primary source."""
    global activation_cache
    
    if activation_cache is not None:
        return activation_cache
    
    # Try SQLite first if available
    if SQLITE_AVAILABLE:
        try:
            import sqlite3
            conn = sqlite3.connect(str(SQLITE_DB))
            conn.row_factory = sqlite3.Row
            
            # Get all problems
            cursor = conn.execute("""
                SELECT id, slug, title, status, priority, path, created_at, updated_at
                FROM problems
            """)
            
            items = {}
            for row in cursor.fetchall():
                problem = dict(row)
                slug = problem["slug"]
                
                # Get tags
                tag_cursor = conn.execute("SELECT tag FROM tags WHERE problem_id = ?", (problem["id"],))
                tags = [r["tag"] for r in tag_cursor.fetchall()]
                
                # Get access times
                access_cursor = conn.execute("""
                    SELECT accessed_at FROM access_log 
                    WHERE problem_id = ? 
                    ORDER BY accessed_at ASC
                """, (problem["id"],))
                access_times = [r["accessed_at"] for r in access_cursor.fetchall()]
                
                items[slug] = {
                    "slug": slug,
                    "path": problem.get("path", f"memory/problems/{slug}.md"),
                    "created": problem["created_at"],
                    "access_times": access_times,
                    "access_count": len(access_times),
                    "activation": 0.5,  # Will be recalculated when needed
                    "tags": tags
                }
            
            conn.close()
            
            activation_cache = {
                "version": "1.0",
                "last_updated": datetime.now(timezone.utc).isoformat(),
                "items": items
            }
            return activation_cache
        except Exception as e:
            logger.warning(f"SQLite load failed ({e}), falling back to JSON")
    
    # Fallback to JSON
    try:
        if ACTIVATION_LOG.exists():
            with open(ACTIVATION_LOG) as f:
                data = json.load(f)
                activation_cache = data
                return data
    except json.JSONDecodeError as e:
        logger.warning(f"activation-log.json is corrupt: {e}")
    except Exception as e:
        logger.warning(f"Could not load activation-log: {e}")
    
    activation_cache = {"version": "1.0", "last_updated": None, "items": {}}
    return activation_cache


def save_activation_log(data):
    """Save the activation log to both SQLite and JSON."""
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    
    # Save to JSON (backup)
    with open(ACTIVATION_LOG, "w") as f:
        json.dump(data, f, indent=2)
    
    # Also update SQLite if available
    if SQLITE_AVAILABLE:
        try:
            import sqlite3
            conn = sqlite3.connect(str(SQLITE_DB))
            
            for slug, item_data in data.get("items", {}).items():
                # Update problem timestamp if there's an access time
                access_times = item_data.get("access_times", [])
                if access_times:
                    conn.execute("""
                        UPDATE problems SET updated_at = ? WHERE slug = ?
                    """, (access_times[-1], slug))
            
            conn.commit()
            conn.close()
        except Exception as e:
            logger.warning(f"Failed to sync to SQLite: {e}")
    
    global activation_cache
    activation_cache = data

def calculate_activation(item_data: Dict[str, Any], current_time: datetime) -> float:
    """
    Calculate ACT-R style activation with freshness-aware decay:
    A = B + Σ(Sᵢ / Dᵢ) - F
    
    Simplified: A = B + recency_score + frequency_bonus - decay
    
    Now with status-aware decay:
    - Resolved problems >30 days decay 2x faster
    - Dead-end problems >60 days decay 3x faster
    
    Returns:
        float: Activation score clamped between 0.0 and 1.0
    """
    access_times = item_data.get("access_times", [])
    if not access_times:
        return BASE_LEVEL
    
    # Calculate recency (most recent access)
    last_access = datetime.fromisoformat(access_times[-1].replace("Z", "+00:00"))
    seconds_ago = (current_time - last_access).total_seconds()
    recency = 1.0 / ((seconds_ago / 3600) + 1)  # hours since last access
    
    # Frequency bonus
    frequency = len(access_times)
    frequency_bonus = 0.1 * (frequency - 1)
    
    # Age decay
    age = (current_time - datetime.fromisoformat(
        item_data["created"].replace("Z", "+00:00")
    )).total_seconds() / 86400  # days old
    
    # Apply freshness-aware decay multiplier
    freshness_multiplier = calculate_freshness_decay(item_data, current_time)
    decay = DECAY_CONSTANT * (age ** 0.5) * freshness_multiplier
    
    activation = BASE_LEVEL + recency * 0.4 + frequency_bonus - decay
    return max(0.0, min(1.0, activation))  # Clamp to 0-1


def get_related_by_tags(slug: str, data: Dict[str, Any]) -> List[Tuple[str, int]]:
    """
    Get slugs that share tags with the given slug (tag priming).
    
    Returns:
        List of tuples (slug, shared_tag_count) sorted by shared tags
    """
    if slug not in data["items"]:
        return []
    
    target_tags = set(data["items"][slug].get("tags", []))
    if not target_tags:
        # Try to load tags from the markdown file
        path = data["items"][slug].get("path", f"memory/problems/{slug}.md")
        tags = load_tags_from_file(path)
        if tags:
            data["items"][slug]["tags"] = tags
            target_tags = set(tags)
            save_activation_log(data)
    
    if not target_tags:
        return []
    
    related = []
    for other_slug, item in data["items"].items():
        if other_slug == slug:
            continue
        other_tags = set(item.get("tags", []))
        if not other_tags:
            # Try to load from file
            other_path = item.get("path", f"memory/problems/{other_slug}.md")
            other_tags = set(load_tags_from_file(other_path))
            if other_tags:
                item["tags"] = list(other_tags)
        
        shared = target_tags & other_tags
        if shared:
            # Return with count of shared tags
            related.append((other_slug, len(shared)))
    
    # Sort by number of shared tags
    related.sort(key=lambda x: x[1], reverse=True)
    return related[:5]  # Top 5 related


def load_tags_from_file(path):
    """Load tags from a problem markdown file."""
    try:
        # Validate path before reading
        if not validate_path(path):
            return []
        
        full_path = SAFE_BASE_DIR / path
        if not full_path.exists():
            return []
        
        content = full_path.read_text()
        # Look for **Tags:** line
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('**Tags:**'):
                # Extract tags from the line
                tags_str = line.replace('**Tags:**', '').strip()
                if tags_str:
                    return [t.strip().rstrip(',') for t in tags_str.split() if t.strip()]
    except Exception as e:
        pass
    return []


def record_access_with_priming(slug: str) -> float:
    """
    Record access and boost related problems that share tags.
    This is tag priming - inspired by Hopfield networks / associative memory.
    
    Returns:
        float: The activation score of the accessed problem
    """
    data = load_activation_log()
    current_time = datetime.now(timezone.utc)
    
    # First, record the main access
    if slug in data["items"]:
        item = data["items"][slug]
        item["access_times"].append(current_time.isoformat())
        item["access_count"] = item.get("access_count", 0) + 1
    else:
        # New item, create entry
        data["items"][slug] = {
            "slug": slug,
            "path": f"memory/problems/{slug}.md",
            "created": current_time.isoformat(),
            "access_times": [current_time.isoformat()],
            "access_count": 1,
            "tags": []
        }
    
    # Recalculate main activation
    data["items"][slug]["activation"] = calculate_activation(
        data["items"][slug], current_time
    )
    
    # TAG PRIMING: Boost related items that share tags
    related = get_related_by_tags(slug, data)
    priming_boost = 0.05  # Small boost per shared tag
    
    for related_slug, shared_count in related:
        if related_slug in data["items"]:
            # Apply small activation boost to related items
            current = data["items"][related_slug].get("activation", BASE_LEVEL)
            boost = priming_boost * shared_count
            data["items"][related_slug]["activation"] = min(1.0, current + boost)
            logger.debug(f"Primed {related_slug}: +{boost:.3f} (shared tags: {shared_count})")
    
    save_activation_log(data)
    
    # Also write to SQLite if available
    if SQLITE_AVAILABLE:
        try:
            db_record_access(slug)
        except Exception as e:
            logger.warning(f"Failed to record access in SQLite: {e}")
    
    return data["items"][slug]["activation"]


def record_access(slug: str) -> float:
    """
    Record that a problem was accessed.
    
    Returns:
        float: The new activation score
    """
    data = load_activation_log()
    current_time = datetime.now(timezone.utc)
    
    if slug in data["items"]:
        item = data["items"][slug]
        item["access_times"].append(current_time.isoformat())
        item["access_count"] = item.get("access_count", 0) + 1
    else:
        # New item, create entry
        data["items"][slug] = {
            "slug": slug,
            "path": f"memory/problems/{slug}.md",
            "created": current_time.isoformat(),
            "access_times": [current_time.isoformat()],
            "access_count": 1,
            "tags": []
        }
    
    # Recalculate activation
    data["items"][slug]["activation"] = calculate_activation(
        data["items"][slug], current_time
    )
    
    save_activation_log(data)
    return data["items"][slug]["activation"]


def sanitize_query(query):
    """
    Sanitize user query to prevent injection attacks.
    
    Removes dangerous characters while preserving meaningful query content.
    
    Args:
        query: Raw user query string
        
    Returns:
        str: Sanitized query safe for shell commands
    """
    if not query:
        return ""
    # Keep only word characters, spaces, and hyphens
    import re
    sanitized = re.sub(r'[^\w\s\-]', '', query).strip()
    return sanitized


def search_qmd(query: str, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    Run QMD search with caching for 5-20x speedup on repeated queries.
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
        
    Returns:
        List of dicts with slug, path, and qmd_score
    """
    # Check cache first
    cached = get_cached_results(query)
    if cached is not None:
        return cached[:max_results]
    
    # Input sanitization
    sanitized = sanitize_query(query)
    if not sanitized:
        return []
    
    try:
        result = subprocess.run(
            ["qmd", "search", sanitized],
            capture_output=True,
            text=True,
            timeout=10
        )
        
        results = []
        for line in result.stdout.split("\n"):
            if "memory/problems" in line or "qmd://memory" in line:
                # Parse: qmd://path or just path:score
                if "qmd://" in line:
                    path_part = line.split("qmd://")[-1].split(":")[0]
                    score = 0.5
                else:
                    parts = line.split(":")
                    if len(parts) >= 2:
                        path_part = parts[0].strip()
                        try:
                            score = float(parts[-1].strip().replace("%", "").replace("#", "")) / 100
                        except:
                            score = 0.5
                
                slug = Path(path_part).stem
                results.append({"slug": slug, "path": path_part, "qmd_score": score})
        
        # Cache results for future calls
        set_cached_results(query, results)
        return results[:max_results]
    except FileNotFoundError:
        logger.warning("qmd command not found")
        return []
    except subprocess.TimeoutExpired:
        logger.warning(f"qmd search timed out for query: {query}")
        return []
    except Exception as e:
        logger.warning(f"QMD search error: {e}")
        return []  # Graceful degradation: return empty results


def load_tag_graph() -> Dict[str, Any]:
    """Load the tag graph."""
    if TAG_GRAPH_PATH.exists():
        with open(TAG_GRAPH_PATH) as f:
            return json.load(f)
    return {"nodes": {}, "edges": [], "tag_index": {}}


def load_pagerank_scores() -> Dict[str, float]:
    """Load PageRank scores with error handling."""
    try:
        if PAGERANK_SCORES_PATH.exists():
            with open(PAGERANK_SCORES_PATH) as f:
                data = json.load(f)
                return data.get("scores", {})
    except json.JSONDecodeError as e:
        logger.warning(f"pagerank-scores.json is corrupt: {e}")
    except Exception as e:
        logger.warning(f"Could not load pagerank-scores: {e}")
    return {}


def get_relationship_score(slug: str, problem_path: Optional[str] = None) -> float:
    """
    Check if problem has explicit relationships to query-related problems.
    
    Looks for ## Relationships section in problem file.
    Returns normalized score (0-1) based on number of relationships.
    
    Returns:
        float: Relationship score between 0.0 and 1.0
    """
    if problem_path is None:
        problem_path = f"memory/problems/{slug}.md"
    
    try:
        # Validate path before reading
        if not validate_path(problem_path):
            return 0.0
        
        full_path = SAFE_BASE_DIR / problem_path
        if not full_path.exists():
            return 0.0
        
        content = full_path.read_text()
        
        # Look for ## Relationships section
        in_relationships = False
        relationship_count = 0
        
        for line in content.split('\n'):
            line_stripped = line.strip()
            
            if line_stripped == "## Relationships":
                in_relationships = True
                continue
            
            # Check for next section (## or end of file)
            if in_relationships and line_stripped.startswith("## "):
                break
            
            # Count non-empty lines in relationships section
            if in_relationships and line_stripped and not line_stripped.startswith('#'):
                # Check for links (related:, conversation:, etc.)
                if any(x in line_stripped.lower() for x in ['related:', 'conversation:', 'file:']):
                    relationship_count += 1
        
        # Also check ## Linked section as fallback
        if relationship_count == 0:
            in_linked = False
            for line in content.split('\n'):
                line_stripped = line.strip()
                
                if line_stripped == "## Linked":
                    in_linked = True
                    continue
                
                if in_linked and line_stripped.startswith("## "):
                    break
                
                if in_linked and line_stripped and line_stripped.startswith('-'):
                    relationship_count += 1
        
        # Normalize: more relationships = higher score (max 1.0)
        if relationship_count == 0:
            return 0.0
        
        return min(1.0, relationship_count / 5.0)  # 5+ relationships = max score
    
    except Exception as e:
        return 0.0


def unified_search(query: str, max_results: int = 5) -> List[Dict[str, Any]]:
    """
    Unified search: QMD + Activation + PageRank + Relationships
    
    Final = 0.30×QMD + 0.30×Activation + 0.25×PageRank + 0.15×Relationships
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
    
    Returns:
        List of dicts with all scores and final ranking
    """
    # Sanitize query before processing
    query = sanitize_query(query)
    if not query:
        return []
    
    data = load_activation_log()
    current_time = datetime.now(timezone.utc)
    
    # Load PageRank scores
    pagerank_scores = load_pagerank_scores()
    
    # Get QMD results
    qmd_results = search_qmd(query, max_results=15)
    
    if not qmd_results:
        return []
    
    # Get query keywords for relationship matching
    query_keywords = set(query.lower().split())
    
    # Combine all signals
    combined = []
    for item in qmd_results:
        slug = item["slug"]
        
        # 1. QMD score (normalized)
        qmd_score = item["qmd_score"]
        
        # 2. Activation score
        if slug in data["items"]:
            activation = calculate_activation(data["items"][slug], current_time)
        else:
            activation = BASE_LEVEL
        
        # 3. PageRank score
        pagerank = pagerank_scores.get(slug, 0.0)
        
        # 4. Relationship score
        problem_path = item.get("path", f"memory/problems/{slug}.md")
        relationship_score = get_relationship_score(slug, problem_path)
        
        # 5. Exact match bonus: boost if query words appear in slug/title
        slug_lower = slug.lower()
        query_words = query.lower().split()
        match_bonus = sum(1 for w in query_words if w in slug_lower) / max(len(query_words), 1)
        exact_bonus = match_bonus * EXACT_MATCH_BONUS_DEFAULT
        
        # Calculate final score with weights
        final_score = (
            WEIGHT_QMD * qmd_score +
            WEIGHT_ACTIVATION * activation +
            WEIGHT_PAGERANK * pagerank +
            WEIGHT_RELATIONSHIPS * relationship_score +
            exact_bonus
        )
        
        combined.append({
            "slug": slug,
            "path": item["path"],
            "qmd_score": qmd_score,
            "activation": activation,
            "pagerank": pagerank,
            "relationship_score": relationship_score,
            "exact_bonus": exact_bonus,
            "final_score": final_score
        })
    
    # Sort by final score
    combined.sort(key=lambda x: x["final_score"], reverse=True)
    
    return combined[:max_results]


def main():
    import sys
    
    parser = argparse.ArgumentParser(description="ACT-R Style Memory Ranker")
    parser.add_argument("query", nargs="?", help="Search query")
    parser.add_argument("--access", metavar="SLUG", help="Record access for a problem slug")
    parser.add_argument("--list", action="store_true", help="List all problems with activation scores")
    parser.add_argument("--json", action="store_true", help="Output results as JSON")
    parser.add_argument("--debug", action="store_true", help="Enable debug logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Suppress logging output")
    
    args = parser.parse_args()
    
    # Setup logging
    logger = setup_logging(debug=args.debug, quiet=args.quiet)
    
    if args.access:
        slug = args.access
        logger.info(f"Recording access for {slug} (with tag priming)...")
        activation = record_access_with_priming(slug)
        logger.info(f"Recorded access for {slug}, activation: {activation:.3f}")
        return
    
    if args.list:
        data = load_activation_log()
        current_time = datetime.now(timezone.utc)
        
        if args.json:
            results = []
            for slug, item in data["items"].items():
                act = calculate_activation(item, current_time)
                results.append({
                    "slug": slug,
                    "activation": act,
                    "access_count": item.get("access_count", 0)
                })
            print(json.dumps(results, indent=2))
        else:
            for slug, item in data["items"].items():
                act = calculate_activation(item, current_time)
                logger.info(f"{slug}: activation={act:.3f}, accesses={item['access_count']}")
        return
    
    if not args.query:
        parser.print_help()
        sys.exit(1)
    
    query = args.query
    results = unified_search(query)
    
    if args.json:
        # Output as JSON
        output = {
            "query": query,
            "weights": {
                "qmd": WEIGHT_QMD,
                "activation": WEIGHT_ACTIVATION,
                "pagerank": WEIGHT_PAGERANK,
                "relationships": WEIGHT_RELATIONSHIPS
            },
            "results": results
        }
        print(json.dumps(output, indent=2))
        return
    
    print(f"\n=== Unified Search: '{query}' ===\n")
    print(f"Weights: QMD={WEIGHT_QMD} | Activation={WEIGHT_ACTIVATION} | PageRank={WEIGHT_PAGERANK} | Relationships={WEIGHT_RELATIONSHIPS}\n")
    
    for i, r in enumerate(results, 1):
        print(f"{i}. {r['slug']}")
        print(f"   QMD: {r['qmd_score']:.2f} | Activation: {r['activation']:.2f} | PageRank: {r['pagerank']:.2f} | Relationships: {r['relationship_score']:.2f} | Final: {r['final_score']:.2f}")
        print(f"   Path: {r['path']}")
        print()


if __name__ == "__main__":
    main()
