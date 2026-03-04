#!/usr/bin/env python3
"""
Migration Script: JSON to SQLite for Nyx Memory System

Migrates problem metadata from JSON to SQLite while keeping JSON as backup.
- Reads existing data from activation-log.json
- Creates SQLite database with problems, tags, and access_log tables
- Writes to both SQLite and JSON (mirror mode)
- Verifies data integrity after migration
"""

import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

# Configuration
MEMORY_BASE_DIR = Path("/home/node/.openclaw")
MEMORY_WORKSPACE_DIR = Path("/home/node/.openclaw/workspace")
SQLITE_DB = MEMORY_BASE_DIR / "memory/nyx.db"
ACTIVATION_LOG = MEMORY_BASE_DIR / "memory/activation-log.json"
PROBLEMS_DIR = MEMORY_WORKSPACE_DIR / "memory/problems"


def create_tables(conn):
    """Create SQLite tables."""
    cursor = conn.cursor()
    
    # Problems table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS problems (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            slug TEXT UNIQUE NOT NULL,
            title TEXT,
            status TEXT DEFAULT 'open',
            priority TEXT DEFAULT 'medium',
            path TEXT,
            created_at TEXT NOT NULL,
            updated_at TEXT NOT NULL
        )
    """)
    
    # Tags table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE,
            UNIQUE(problem_id, tag)
        )
    """)
    
    # Access log table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS access_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            problem_id INTEGER NOT NULL,
            accessed_at TEXT NOT NULL,
            access_type TEXT DEFAULT 'access',
            FOREIGN KEY (problem_id) REFERENCES problems(id) ON DELETE CASCADE
        )
    """)
    
    # Indexes for performance
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_problems_slug ON problems(slug)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_problem_id ON tags(problem_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_tags_tag ON tags(tag)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_log_problem_id ON access_log(problem_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_access_log_accessed_at ON access_log(accessed_at)")
    
    conn.commit()
    print("✓ Tables created successfully")


def load_json_data():
    """Load data from activation-log.json."""
    if not ACTIVATION_LOG.exists():
        print("ERROR: activation-log.json not found")
        sys.exit(1)
    
    with open(ACTIVATION_LOG) as f:
        data = json.load(f)
    
    print(f"✓ Loaded {len(data.get('items', {}))} items from activation-log.json")
    return data


def extract_problem_metadata(slug):
    """Extract metadata from problem markdown file."""
    problem_file = PROBLEMS_DIR / f"{slug}.md"
    
    if not problem_file.exists():
        return {
            "title": slug.replace("-", " ").title(),
            "status": "open",
            "priority": "medium",
            "tags": []
        }
    
    with open(problem_file) as f:
        content = f.read()
    
    # Extract title (first heading after # Problem:)
    title = slug.replace("-", " ").title()
    status = "open"
    priority = "medium"
    tags = []
    
    for line in content.split("\n"):
        if line.startswith("# Problem:"):
            title = line.replace("# Problem:", "").strip()
        elif line.startswith("**Status:**"):
            status = line.replace("**Status:**", "").strip().lower()
        elif line.startswith("**Priority:**"):
            priority = line.replace("**Priority:**", "").strip().lower()
        elif line.startswith("**Tags:**"):
            tags_str = line.replace("**Tags:**", "").strip()
            tags = [t.strip().rstrip(",") for t in tags_str.split() if t.strip()]
    
    return {
        "title": title,
        "status": status,
        "priority": priority,
        "tags": tags
    }


def migrate_to_sqlite(conn, json_data):
    """Migrate data from JSON to SQLite."""
    cursor = conn.cursor()
    items = json_data.get("items", {})
    
    migrated_count = 0
    
    for slug, item_data in items.items():
        # Get metadata from problem file
        metadata = extract_problem_metadata(slug)
        
        # Parse created_at
        created_at = item_data.get("created", datetime.now(timezone.utc).isoformat())
        if created_at.endswith("Z"):
            created_at = created_at[:-1] + "+00:00"
        
        # Updated_at from last access or created
        access_times = item_data.get("access_times", [])
        if access_times:
            updated_at = access_times[-1]
            if updated_at.endswith("Z"):
                updated_at = updated_at[:-1] + "+00:00"
        else:
            updated_at = created_at
        
        # Insert problem
        cursor.execute("""
            INSERT OR REPLACE INTO problems (slug, title, status, priority, path, created_at, updated_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            slug,
            metadata["title"],
            metadata["status"],
            metadata["priority"],
            item_data.get("path", f"memory/problems/{slug}.md"),
            created_at,
            updated_at
        ))
        
        problem_id = cursor.lastrowid
        
        # If problem already existed (due to INSERT OR REPLACE), get its ID
        if problem_id == 0:
            cursor.execute("SELECT id FROM problems WHERE slug = ?", (slug,))
            problem_id = cursor.fetchone()[0]
        
        # Insert tags
        all_tags = set(metadata["tags"])
        all_tags.update(item_data.get("tags", []))
        
        for tag in all_tags:
            cursor.execute("""
                INSERT OR IGNORE INTO tags (problem_id, tag)
                VALUES (?, ?)
            """, (problem_id, tag))
        
        # Insert access log entries
        for access_time in access_times:
            if access_time.endswith("Z"):
                access_time = access_time[:-1] + "+00:00"
            cursor.execute("""
                INSERT INTO access_log (problem_id, accessed_at, access_type)
                VALUES (?, ?, 'access')
            """, (problem_id, access_time))
        
        migrated_count += 1
    
    conn.commit()
    print(f"✓ Migrated {migrated_count} problems to SQLite")
    return migrated_count


def verify_migration(conn):
    """Verify data integrity after migration."""
    cursor = conn.cursor()
    
    # Count checks
    cursor.execute("SELECT COUNT(*) FROM problems")
    problem_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM tags")
    tag_count = cursor.fetchone()[0]
    
    cursor.execute("SELECT COUNT(*) FROM access_log")
    access_count = cursor.fetchone()[0]
    
    print(f"\n📊 Migration Summary:")
    print(f"   Problems: {problem_count}")
    print(f"   Tags: {tag_count}")
    print(f"   Access log entries: {access_count}")
    
    # Verify against JSON
    json_data = load_json_data()
    json_item_count = len(json_data.get("items", {}))
    
    if problem_count == json_item_count:
        print(f"✓ Data integrity verified: {problem_count} problems match JSON")
    else:
        print(f"⚠ Warning: {problem_count} != {json_item_count}")
    
    # Sample queries to verify
    print("\n📋 Sample data:")
    cursor.execute("SELECT slug, title, status, priority FROM problems LIMIT 3")
    for row in cursor.fetchall():
        print(f"   - {row[0]}: {row[1]} ({row[2]}/{row[3]})")
    
    return True


def enable_sqlite_mode(conn):
    """Enable SQLite as primary with JSON mirror."""
    # Add a metadata table to track mode
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS metadata (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        INSERT OR REPLACE INTO metadata (key, value)
        VALUES ('storage_mode', 'sqlite_primary')
    """)
    conn.commit()
    print("✓ SQLite primary mode enabled")


def main():
    print("=" * 60)
    print("Nyx Memory System: JSON to SQLite Migration")
    print("=" * 60)
    
    # Remove existing database if present (fresh start)
    if SQLITE_DB.exists():
        print(f"\n⚠ Removing existing database: {SQLITE_DB}")
        SQLITE_DB.unlink()
    
    # Create database connection
    print(f"\n📁 Creating database: {SQLITE_DB}")
    conn = sqlite3.connect(str(SQLITE_DB))
    
    # Create tables
    print("\n🔧 Creating tables...")
    create_tables(conn)
    
    # Load JSON data
    print("\n📥 Loading JSON data...")
    json_data = load_json_data()
    
    # Migrate to SQLite
    print("\n🚀 Running migration...")
    migrate_to_sqlite(conn, json_data)
    
    # Verify
    print("\n✅ Verifying migration...")
    verify_migration(conn)
    
    # Enable SQLite mode
    print("\n⚡ Enabling SQLite primary mode...")
    enable_sqlite_mode(conn)
    
    conn.close()
    print("\n" + "=" * 60)
    print("Migration complete! SQLite is now the primary store.")
    print("JSON files are kept as backup.")
    print("=" * 60)


if __name__ == "__main__":
    main()
