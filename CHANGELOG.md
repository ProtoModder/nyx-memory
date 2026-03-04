# Changelog - SQLite Backend Migration

## Date: 2026-03-04

### New Feature: SQLite Backend for Problem Metadata

Added SQLite database as the primary storage for problem metadata, with JSON as mirror backup.

#### Changes Made:

1. **New SQLite Database** (`~/.openclaw/memory/nyx.db`)
   - `problems` table: id, slug, title, status, priority, path, created_at, updated_at
   - `tags` table: id, problem_id, tag
   - `access_log` table: id, problem_id, accessed_at, access_type
   - Indexes on slug, tag, and access times for fast queries

2. **New Files:**
   - `migrate_to_sqlite.py` - One-time migration script
   - `db.py` - SQLite backend module with CRUD operations

3. **Modified Files:**
   - `actr_ranker.py` - Updated to read from SQLite first, fallback to JSON

#### Features:
- **Read from SQLite**: Primary data source for faster queries
- **Write to both**: All writes go to SQLite and JSON (mirror)
- **Auto-create problems**: Non-existing problems auto-created on access
- **Fallback**: If SQLite unavailable, falls back to JSON

#### Usage:
```bash
# Run migration (one-time)
python3 ~/.openclaw/memory/migrate_to_sqlite.py

# Using the db module directly
python3 -c "from db import get_problem, search_problems, get_stats"

# Query stats
python3 -c "from db import get_stats; print(get_stats())"
```

#### Data Integrity:
- 52 problems migrated from JSON
- 165 tags migrated
- 61 access log entries migrated
- Verified: same problems in both SQLite and JSON

---

# Changelog - Memory Visualizations

## Date: 2026-03-04

### New Feature: ASCII Memory Visualizations

Added a new visualization module for the Nyx Memory System with ASCII-based visualizations.

#### Features:

1. **Tag Cloud** (`--tags`)
   - Shows most common tags with frequency counts
   - Color gradient based on usage (red = high, orange/yellow = medium, white = low)
   - Size indicators (●●● to ○○○)

2. **Relationship Graph** (`--graph`)
   - ASCII adjacency matrix showing memory connections
   - Nodes sorted by activation score
   - Shows tag-based connections between memories
   - Legend for connection strength

3. **Activation Timeline** (`--timeline`)
   - Shows recently accessed memories
   - Relative timestamps (just now, Xm ago, Xh ago, Xd ago)
   - Access count indicators
   - Color-coded by recency

4. **Memory Health Dashboard** (`--dashboard`)
   - Overall health score (EXCELLENT/HEALTHY/FAIR/NEEDS ATTENTION)
   - Total memories, tags, connections, accesses
   - Activation distribution bar chart
   - Average metrics (activation, PageRank, never accessed)

#### Usage:

```bash
# Show all visualizations
python3 ~/.openclaw/memory/visualize.py --all

# Show specific visualization
python3 ~/.openclaw/memory/visualize.py --dashboard
python3 ~/.openclaw/memory/visualize.py --tags
python3 ~/.openclaw/memory/visualize.py --graph
python3 ~/.openclaw/memory/visualize.py --timeline
```

#### Importable Functions:

```python
from visualize import (
    show_dashboard,
    show_tag_cloud,
    show_relationship_graph,
    show_activation_timeline
)
```

#### Files Added:
- `~/.openclaw/memory/visualize.py`

#### Requirements:
- Uses existing data files: activation-log.json, tag-graph.json, pagerank-scores.json
- Uses ANSI colors (compatible with most terminals)

---

# Changelog - Nyx Memory TUI

## Date: 2026-03-04

### New Feature: Interactive TUI

Added an interactive Text User Interface (TUI) for the Nyx Memory System.

#### Features:

1. **Menu-driven interface** - Numbered menu options for easy navigation
2. **Search with live results** - Query memory and see ranked results
3. **List recent problems** - Show recently accessed problems with status/tags
4. **View problem details** - Preview problem content and metadata
5. **Record access** - Manually record access to problems (boosts activation)
6. **Show tags** - View all tags and their associated problems
7. **Clear cache** - Clear the query cache

#### Technical Details:

- Uses ANSI color codes (from actr_ranker.py) for colorized output
- Pure Python with standard library (no curses dependency)
- Uses input() for cross-platform compatibility
- Auto-records access when viewing problems

#### Files Added:
- `~/.openclaw/memory/nyx_tui.py` (executable)

#### Usage:
```bash
python3 ~/.openclaw/memory/nyx_tui.py
```

---

# Changelog - Input Sanitization Enhancements

## Date: 2026-03-04

### Security Improvements

Added comprehensive input sanitization to prevent directory traversal, shell injection, and DoS attacks.

#### Changes Made:

1. **New `validate_slug()` function**
   - Validates slugs contain only alphanumeric, hyphen, underscore
   - Rejects directory traversal attempts (`..`, `/`, `\`)
   - Enforces max length of 200 characters

2. **New `sanitize_query()` function**
   - Validates query is not empty
   - Enforces max length of 1000 characters
   - Removes null bytes and dangerous characters

3. **Input validation added to all entry points:**
   - `unified_search()` - query sanitization
   - `fast_search()` - query sanitization  
   - `tiered_search()` - query sanitization
   - `combined_search()` - query sanitization
   - `record_access_with_priming()` - slug validation
   - CLI main function - slug validation

4. **`validate_path()` already in place:**
   - `cached_read()` uses validate_path() to prevent directory traversal
   - All file reads go through this validated path

### Test Results:

- Path traversal `../../../etc/passwd` → Returns empty/error
- Empty query → Returns empty with error message  
- Null byte injection → Stripped, returns results
- Invalid slug characters → Rejected with clear error
- Valid queries/slugs → Work correctly

### Files Modified:
- `~/.openclaw/memory/actr_ranker.py`
