#!/usr/bin/env python3
"""
SQLite Backend for Nyx Memory System

Provides read/write access to problem metadata stored in SQLite.
Keeps JSON files as mirror (write to both).

Usage:
    from db import get_problem, update_problem, record_access, search_problems
"""

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

# Configuration
MEMORY_BASE_DIR = Path("/home/node/.openclaw")
MEMORY_WORKSPACE_DIR = Path("/home/node/.openclaw/workspace")
SQLITE_DB = MEMORY_BASE_DIR / "memory/nyx.db"
ACTIVATION_LOG = MEMORY_BASE_DIR / "memory/activation-log.json"

# Connection pool
_conn = None


def get_connection():
    """Get SQLite connection (singleton)."""
    global _conn
    if _conn is None:
        _conn = sqlite3.connect(str(SQLITE_DB))
        _conn.row_factory = sqlite3.Row
    return _conn


def is_sqlite_available():
    """Check if SQLite database exists and is usable."""
    try:
        conn = get_connection()
        conn.execute("SELECT 1 FROM problems LIMIT 1")
        return True
    except:
        return False


# ============================================================================
# Problem Operations
# ============================================================================

def get_problem(slug: str) -> Optional[dict]:
    """Get problem by slug."""
    conn = get_connection()
    cursor = conn.execute("""
        SELECT id, slug, title, status, priority, path, created_at, updated_at
        FROM problems WHERE slug = ?
    """, (slug,))
    
    row = cursor.fetchone()
    if not row:
        return None
    
    problem = dict(row)
    
    # Get tags
    cursor = conn.execute("SELECT tag FROM tags WHERE problem_id = ?", (problem["id"],))
    problem["tags"] = [r["tag"] for r in cursor.fetchall()]
    
    # Get access count
    cursor = conn.execute("SELECT COUNT(*) as count FROM access_log WHERE problem_id = ?", (problem["id"],))
    problem["access_count"] = cursor.fetchone()["count"]
    
    # Get last access
    cursor = conn.execute("SELECT accessed_at FROM access_log WHERE problem_id = ? ORDER BY accessed_at DESC LIMIT 1", (problem["id"],))
    last_access = cursor.fetchone()
    problem["last_access"] = last_access["accessed_at"] if last_access else None
    
    return problem


def get_all_problems() -> list:
    """Get all problems."""
    conn = get_connection()
    cursor = conn.execute("""
        SELECT id, slug, title, status, priority, path, created_at, updated_at
        FROM problems ORDER BY updated_at DESC
    """)
    
    problems = []
    for row in cursor.fetchall():
        problem = dict(row)
        
        # Get tags
        tag_cursor = conn.execute("SELECT tag FROM tags WHERE problem_id = ?", (problem["id"],))
        problem["tags"] = [r["tag"] for r in tag_cursor.fetchall()]
        
        # Get access count
        count_cursor = conn.execute("SELECT COUNT(*) as count FROM access_log WHERE problem_id = ?", (problem["id"],))
        problem["access_count"] = count_cursor.fetchone()["count"]
        
        problems.append(problem)
    
    return problems


def create_problem(slug: str, title: str, status: str = "open", 
                   priority: str = "medium", tags: list = None) -> int:
    """Create a new problem. Returns problem ID."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    
    conn.execute("""
        INSERT INTO problems (slug, title, status, priority, path, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (slug, title, status, priority, f"memory/problems/{slug}.md", now, now))
    
    problem_id = conn.lastrowid
    
    # Add tags
    if tags:
        for tag in tags:
            conn.execute("INSERT INTO tags (problem_id, tag) VALUES (?, ?)", (problem_id, tag))
    
    conn.commit()
    
    # Mirror to JSON
    _mirror_to_json()
    
    return problem_id


def update_problem(slug: str, **kwargs) -> bool:
    """Update problem fields. Returns True if updated."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    
    # Build update query
    allowed_fields = ["title", "status", "priority"]
    updates = []
    values = []
    
    for field in allowed_fields:
        if field in kwargs:
            updates.append(f"{field} = ?")
            values.append(kwargs[field])
    
    if not updates:
        return False
    
    updates.append("updated_at = ?")
    values.append(now)
    values.append(slug)
    
    conn.execute(f"""
        UPDATE problems SET {', '.join(updates)} WHERE slug = ?
    """, values)
    
    # Update tags if provided
    if "tags" in kwargs:
        # Remove existing tags
        conn.execute("DELETE FROM tags WHERE problem_id = (SELECT id FROM problems WHERE slug = ?)", (slug,))
        # Add new tags
        problem_id = conn.execute("SELECT id FROM problems WHERE slug = ?", (slug,)).fetchone()["id"]
        for tag in kwargs["tags"]:
            conn.execute("INSERT INTO tags (problem_id, tag) VALUES (?, ?)", (problem_id, tag))
    
    conn.commit()
    
    # Mirror to JSON
    _mirror_to_json()
    
    return True


def delete_problem(slug: str) -> bool:
    """Delete a problem. Returns True if deleted."""
    conn = get_connection()
    cursor = conn.execute("DELETE FROM problems WHERE slug = ?", (slug,))
    conn.commit()
    
    if cursor.rowcount > 0:
        # Mirror to JSON
        _mirror_to_json()
        return True
    return False


# ============================================================================
# Access Log Operations
# ============================================================================

def record_access(slug: str, access_type: str = "access") -> dict:
    """Record an access to a problem. Returns updated problem data."""
    conn = get_connection()
    now = datetime.now(timezone.utc).isoformat()
    
    # Get problem ID, create if doesn't exist
    row = conn.execute("SELECT id FROM problems WHERE slug = ?", (slug,)).fetchone()
    if not row:
        # Auto-create problem
        conn.execute("""
            INSERT INTO problems (slug, title, status, priority, path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            slug,
            slug.replace("-", " ").title(),
            "open",
            "medium",
            f"memory/problems/{slug}.md",
            now,
            now
        ))
        conn.commit()
        row = conn.execute("SELECT id FROM problems WHERE slug = ?", (slug,)).fetchone()
    
    problem_id = row["id"]
    
    # Insert access log
    conn.execute("""
        INSERT INTO access_log (problem_id, accessed_at, access_type)
        VALUES (?, ?, ?)
    """, (problem_id, now, access_type))
    
    # Update problem timestamp
    conn.execute("UPDATE problems SET updated_at = ? WHERE id = ?", (now, problem_id))
    
    conn.commit()
    
    # Mirror to JSON
    _mirror_to_json()
    
    return get_problem(slug)


def get_access_history(slug: str, limit: int = 10) -> list:
    """Get access history for a problem."""
    conn = get_connection()
    
    row = conn.execute("SELECT id FROM problems WHERE slug = ?", (slug,)).fetchone()
    if not row:
        return []
    
    cursor = conn.execute("""
        SELECT accessed_at, access_type 
        FROM access_log 
        WHERE problem_id = ? 
        ORDER BY accessed_at DESC 
        LIMIT ?
    """, (row["id"], limit))
    
    return [dict(r) for r in cursor.fetchall()]


# ============================================================================
# Search Operations
# ============================================================================

def search_problems(query: str = None, status: str = None, 
                    priority: str = None, tag: str = None,
                    limit: int = 50) -> list:
    """Search problems with filters."""
    conn = get_connection()
    
    sql = """
        SELECT DISTINCT p.id, p.slug, p.title, p.status, p.priority, p.created_at, p.updated_at
        FROM problems p
    """
    
    joins = []
    conditions = []
    params = []
    
    if tag:
        joins.append("JOIN tags t ON p.id = t.problem_id")
        conditions.append("t.tag = ?")
        params.append(tag)
    
    if status:
        conditions.append("p.status = ?")
        params.append(status)
    
    if priority:
        conditions.append("p.priority = ?")
        params.append(priority)
    
    if query:
        conditions.append("(p.title LIKE ? OR p.slug LIKE ?)")
        params.extend([f"%{query}%", f"%{query}%"])
    
    if joins:
        sql += " " + " ".join(joins)
    if conditions:
        sql += " WHERE " + " AND ".join(conditions)
    
    sql += " ORDER BY p.updated_at DESC LIMIT ?"
    params.append(limit)
    
    cursor = conn.execute(sql, params)
    
    problems = []
    for row in cursor.fetchall():
        problem = dict(row)
        
        # Get tags
        tag_cursor = conn.execute("SELECT tag FROM tags WHERE problem_id = ?", (problem["id"],))
        problem["tags"] = [r["tag"] for r in tag_cursor.fetchall()]
        
        problems.append(problem)
    
    return problems


def get_problems_by_tag(tag: str) -> list:
    """Get all problems with a specific tag."""
    return search_problems(tag=tag)


def get_problems_by_status(status: str) -> list:
    """Get all problems with a specific status."""
    return search_problems(status=status)


# ============================================================================
# Statistics
# ============================================================================

def get_stats() -> dict:
    """Get database statistics."""
    conn = get_connection()
    
    stats = {}
    
    stats["total_problems"] = conn.execute("SELECT COUNT(*) FROM problems").fetchone()[0]
    stats["total_tags"] = conn.execute("SELECT COUNT(*) FROM tags").fetchone()[0]
    stats["total_accesses"] = conn.execute("SELECT COUNT(*) FROM access_log").fetchone()[0]
    
    # Status breakdown
    cursor = conn.execute("SELECT status, COUNT(*) as count FROM problems GROUP BY status")
    stats["by_status"] = {r["status"]: r["count"] for r in cursor.fetchall()}
    
    # Priority breakdown
    cursor = conn.execute("SELECT priority, COUNT(*) as count FROM problems GROUP BY priority")
    stats["by_priority"] = {r["priority"]: r["count"] for r in cursor.fetchall()}
    
    # Most accessed
    cursor = conn.execute("""
        SELECT p.slug, COUNT(a.id) as access_count
        FROM problems p
        JOIN access_log a ON p.id = a.problem_id
        GROUP BY p.id
        ORDER BY access_count DESC
        LIMIT 10
    """)
    stats["most_accessed"] = [dict(r) for r in cursor.fetchall()]
    
    return stats


# ============================================================================
# JSON Mirror
# ============================================================================

def _mirror_to_json():
    """Mirror SQLite data to JSON (for backup)."""
    if not ACTIVATION_LOG.exists():
        return
    
    try:
        # Read existing JSON to preserve format
        with open(ACTIVATION_LOG) as f:
            json_data = json.load(f)
        
        # Get all problems from SQLite
        problems = get_all_problems()
        
        # Get fresh connection
        conn = get_connection()
        
        items = {}
        for p in problems:
            access_history = conn.execute("""
                SELECT accessed_at FROM access_log 
                WHERE problem_id = ? 
                ORDER BY accessed_at ASC
            """, (p["id"],)).fetchall()
            
            access_times = [r["accessed_at"] for r in access_history]
            
            items[p["slug"]] = {
                "slug": p["slug"],
                "path": p["path"],
                "created": p["created_at"],
                "access_times": access_times,
                "access_count": len(access_times),
                "activation": 0.5,  # Will be recalculated by actr_ranker
                "tags": p.get("tags", [])
            }
        
        json_data["items"] = items
        json_data["last_updated"] = datetime.now(timezone.utc).isoformat()
        
        with open(ACTIVATION_LOG, "w") as f:
            json.dump(json_data, f, indent=2)
    except Exception as e:
        print(f"Warning: Failed to mirror to JSON: {e}")


def rebuild_json_mirror():
    """Rebuild the entire JSON file from SQLite."""
    global _conn
    if _conn:
        _conn.close()
        _conn = None
    
    # Reload from actr_ranker
    from actr_ranker import load_activation_log, save_activation_log
    
    problems = get_all_problems()
    
    # Convert to activation-log format
    items = {}
    conn = get_connection()
    
    for p in problems:
        access_history = conn.execute("""
            SELECT accessed_at FROM access_log 
            WHERE problem_id = ? 
            ORDER BY accessed_at ASC
        """, (p["id"],)).fetchall()
        
        access_times = [r["accessed_at"] for r in access_history]
        
        items[p["slug"]] = {
            "slug": p["slug"],
            "path": p["path"],
            "created": p["created_at"],
            "access_times": access_times,
            "access_count": len(access_times),
            "activation": 0.5,
            "tags": p.get("tags", [])
        }
    
    json_data = load_activation_log()
    json_data["items"] = items
    save_activation_log(json_data)
    
    print(f"✓ Rebuilt JSON mirror with {len(items)} items")
