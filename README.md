# Nyx Memory System

> **⚠️ Experimental / Conceptual** — This is a research project in active testing. Built by Nyx (OpenClaw AI Assistant) for protomodder. Not production-ready.

A hybrid memory retrieval system that combines semantic search, cognitive modeling, and graph theory to surface the most relevant memories. Inspired by the ACT-R (Adaptive Control of Thought—Rational) cognitive architecture, this system models human memory dynamics—recency, frequency, and associative priming—to rank search results intelligently.

---

## Quick Start

```bash
# Search for something you worked on before
python3 actr_ranker.py "tts voice config"

# After working on something, record that you accessed it
python3 actr_ranker.py --access my-problem-slug

# List all tracked items
python3 actr_ranker.py --list

# See all options
python3 actr_ranker.py --help
```

---

## What Is This?

Think of this as your **second brain** — a system that remembers what you forget.

When you're working on a project, you often revisit the same problems, solutions, and research. This system tracks:
- **What** you accessed (recency)
- **How often** you accessed it (frequency)
- **What's connected** to what (relationships)
- **What's globally important** in your knowledge base

The magic is in how it combines all these signals to surface exactly what you need, right when you need it.

---

## Why Does This Exist?

I built this because I kept forgetting solutions I'd already found. You know that feeling — "I'm sure I solved this before..." 

Now instead of relearning everything from scratch, the system:
1. Remembers what you worked on
2. Understands what's related to what
3. Surfaces the right memory at the right time

---

## Installation

### Prerequisites

- **Python 3.8+** 
- **QMD** (Query-Managed Display) — part of OpenClaw's memory infrastructure
- **pyyaml** package

### Quick Install

```bash
# Clone the repository
git clone https://github.com/ProtoModder/nyx-memory.git
cd nyx-memory

# Install dependencies
pip install -r requirements.txt
```

### For OpenClaw Users

If you're already running OpenClaw, the memory system is already set up! Just use the commands above or integrate directly:

```python
import sys
sys.path.insert(0, '/home/node/.openclaw/memory')

from actr_ranker import unified_search, record_access_with_priming

# Search your memories
results = unified_search("tts voice")
for r in results:
    print(f"{r['slug']}: {r['final_score']:.2f}")

# Record that you accessed something
record_access_with_priming("tts-voice-configuration")
```

---

## Usage

### Basic Search

Find memories related to your query:

```bash
python3 actr_ranker.py "your query"

# Example:
python3 actr_ranker.py "voice tts config"
```

### Recording Access

This is the secret sauce. When you access a memory (solve a problem, read research, etc.), record it:

```bash
# Record access (updates activation + triggers tag priming)
python3 actr_ranker.py --access problem-slug

# Example:
python3 actr_ranker.py --access tts-voice-configuration
```

**Why does this matter?** The more you access something, the higher its activation score. This means frequently-used memories float to the top of search results.

### Listing Tracked Items

See all memories and their current activation scores:

```bash
python3 actr_ranker.py --list
```

### Tiered Search

The system automatically chooses the right search strategy:

```bash
# Fast search (QMD only) - for quick lookups
python3 actr_ranker.py --fast "simple query"

# Deep search (unified) - for complex queries  
python3 actr_ranker.py --deep "complex query with many aspects"
```

---

## Real-World Examples

### Example 1: Finding That One Problem You Solved Last Week

You're pretty sure you fixed a similar issue before, but can't remember where you documented it:

```bash
python3 actr_ranker.py "ffmpeg video encoding error"
```

The system searches semantically (finding related concepts) AND prioritizes things you've recently accessed.

### Example 2: After Solving Something New

You just finished debugging a tricky issue. Record it so you can find it later:

```bash
python3 actr_ranker.py --access puppeteer-steam-detection-fix
```

This:
- Boosts the memory's activation score
- Primes related memories (via shared tags)
- Makes it easier to find next time

### Example 3: Exploring Related Work

You found a memory about video processing and want to find everything connected to it:

```bash
# The tag graph automatically surfaces related memories
python3 actr_ranker.py "video processing pipeline"

# Even memories without the exact words get boosted if they share tags
```

### Example 4: Daily Standup — What Did I Work On?

Quick review of recent work:

```bash
# List everything with high activation (recently/frequently accessed)
python3 actr_ranker.py --list | head -20
```

### Example 5: Debugging a Recurring Issue

Something keeps breaking and you want to see all related problems:

```bash
python3 actr_ranker.py "api rate limit"
# Results include:
# - api-rate-limiting-2024 (activated 5 times)
# - rate-limit-429-error (activated 3 times)
# - github-api-throttling (activated 2 times)
```

### Example 6: Pre-Retrieval Check (For Developers)

Before running an expensive search, check if it's needed:

```python
from actr_ranker import should_retrieve_memory, get_retrieval_tier

# Quick check - do we even need to search?
if should_retrieve_memory("fix the login bug"):
    tier = get_retrieval_tier("fix the login bug")
    print(f"Search tier: {tier}")  # 'fast' or 'slow'
```

### Example 7: Freshness — Auto-Deprecating Old Memories

Old, resolved problems naturally fade:

```python
from actr_ranker import apply_freshness_to_all

# Manually trigger freshness decay
apply_freshness_to_all()
# Problems older than 30 days (resolved) or 60 days (dead-end) get penalized
```

---

## Configuration

Edit `config.yaml` to tune the system:

```yaml
weights:
  qmd: 0.50
  activation: 0.15
  pagerank: 0.25
  relationships: 0.10
  exact_match_bonus: 0.10

actr:
  base_level: 0.3
  decay_constant: 0.5
  spreading_strength: 0.2

freshness:
  resolved_days: 30
  dead_end_days: 60

search:
  max_results: 10
  qmd_max_results: 15
```

### When to Tweak Weights

| Scenario | Recommended Weights |
|----------|-------------------|
| **General use** | QMD 0.50, Activation 0.15, PageRank 0.25 |
| **Prefer recent work** | Activation 0.30+, QMD 0.35 |
| **Find related concepts** | QMD 0.60+, PageRank 0.20 |
| **Follow relationships** | Relationships 0.20+, PageRank 0.30 |

---

## Features

- **QMD Semantic Search** — Vector-based similarity matching across your knowledge base
- **ACT-R Activation** — Human memory-inspired scoring based on recency and access frequency
- **PageRank** — Graph centrality that highlights globally important entries
- **Relationships** — Explicit manual links between related problems
- **Exact Match Bonus** — Boosts results when query terms appear in the slug
- **Pre-retrieval Check** — Decides if memory search is needed before running
- **Memory Freshness** — Automatic aging/decay for old problems
- **Fast/Slow Retrieval Tiers** — Quick QMD-only or deep unified search
- **Tag Priming** — When you access a memory, related memories get a small boost

---

## How It Works (The Magic)

The system combines five signals to produce a unified relevance score:

```
Final Score = 0.50×QMD + 0.15×Activation + 0.25×PageRank + 0.10×Relationships + 0.10×ExactMatch
```

### ACT-R Activation Formula

This is the heart of the system — modeled after human memory:

```
A = B + (recency × 0.4) + (frequency_bonus) - (age_decay)

Where:
- B = base level (0.3)
- recency = 1 / (hours since last access + 1)
- frequency_bonus = 0.1 × (access_count - 1)
- age_decay = 0.5 × √(days_old)
```

**What this means:**
- Recently accessed items bubble up
- Frequently accessed items get a permanent boost
- Old items naturally fade (unless you keep accessing them)

### Tag Priming (Hopfield Networks)

When you access a problem, related problems with shared tags get a small activation boost — just like how thinking about one memory triggers related memories.

---

## API Reference

### Core Ranking Functions

#### `unified_search(query, max_results=10)`

The main search function — combines all signals for best results.

```python
from actr_ranker import unified_search

results = unified_search("tts voice config", max_results=5)
# Returns: [{'slug': '...', 'final_score': 0.85, 'qmd_score': 0.9, 'activation': 0.7, ...}]
```

**Parameters:**
- `query` (str) — Search query
- `max_results` (int, default=10) — Maximum results to return

**Returns:** List of result dicts with keys:
- `slug` — Unique identifier
- `final_score` — Combined relevance score (0-1)
- `qmd_score` — Semantic similarity (0-1)
- `activation` — ACT-R activation (0-1)
- `pagerank` — PageRank score (0-1)
- `relationships` — Relationship score (0-1)
- `exact_bonus` — Exact match bonus (0 or 0.1)

#### `search_qmd(query, max_results=15)`

Fast semantic search only — no activation/PageRank.

```python
from actr_ranker import search_qmd

results = search_qmd("video processing", max_results=10)
```

#### `combined_search(query, max_results=5)`

QMD + Activation + Relationships (no PageRank) — faster than unified.

```python
from actr_ranker import combined_search

results = combined_search("api error")
```

#### `fast_search(query, max_results=5)`

Quick QMD-only search for simple lookups.

```python
from actr_ranker import fast_search

results = fast_search("login fix")
```

#### `tiered_search(query, max_results=5, force_deep=False)`

Automatically chooses fast or deep search based on query complexity.

```python
from actr_ranker import tiered_search

# Auto-selects strategy
results = tiered_search("complex multi-aspect query")

# Force deep search
results = tiered_search("simple", force_deep=True)
```

---

### Access Recording

#### `record_access_with_priming(slug)`

Record an access and trigger tag priming.

```python
from actr_ranker import record_access_with_priming

result = record_access_with_priming("my-problem-slug")
# Returns: {'success': True, 'slug': 'my-problem-slug', 'primed': ['related-slug-1', ...]}
```

#### `record_access(slug)`

Simple access recording (no priming).

```python
from actr_ranker import record_access

record_access("tts-voice-config")
```

---

### Pre-Retrieval Functions

#### `should_retrieve_memory(query)`

Check if memory search is worthwhile for this query.

```python
from actr_ranker import should_retrieve_memory

if should_retrieve_memory("fix the login bug"):
    print("Yes, search recommended")
```

**Returns:** `bool`

#### `get_retrieval_tier(query, force_deep=False)`

Determine search strategy.

```python
from actr_ranker import get_retrieval_tier

tier = get_retrieval_tier("my query")
# Returns: 'fast', 'slow', or 'skip'
```

---

### Data Loading Functions

#### `load_activation_log()`

Load the activation log.

```python
from actr_ranker import load_activation_log

data = load_activation_log()
# Returns: {'items': {'slug1': {'access_times': [...], 'created': '...'}, ...}}
```

#### `load_tag_graph()`

Load the tag graph structure.

```python
from actr_ranker import load_tag_graph

graph = load_tag_graph()
# Returns: {'nodes': [...], 'edges': [...]}
```

#### `load_pagerank_scores()`

Load precomputed PageRank scores.

```python
from actr_ranker import load_pagerank_scores

scores = load_pagerank_scores()
# Returns: {'slug1': 0.5, 'slug2': 0.3, ...}
```

#### `load_config()`

Load configuration from config.yaml.

```python
from actr_ranker import load_config

config = load_config()
# Returns: dict with weights, actr, freshness, search settings
```

---

### Utility Functions

#### `calculate_activation(item_data, current_time)`

Calculate ACT-R activation for a single item.

```python
from datetime import datetime
from actr_ranker import calculate_activation, load_activation_log

log = load_activation_log()
item = log['items']['my-slug']
score = calculate_activation(item, datetime.now())
# Returns: float (typically 0.0 - 1.0)
```

#### `get_related_by_tags(slug, data=None)`

Get related slugs via shared tags.

```python
from actr_ranker import get_related_by_tags, load_tag_graph

graph = load_tag_graph()
related = get_related_by_tags("my-slug", graph)
# Returns: ['related-slug-1', 'related-slug-2', ...]
```

#### `apply_freshness_to_all(current_time=None)`

Apply decay to old memories.

```python
from actr_ranker import apply_freshness_to_all

apply_freshness_to_all()
# Penalizes: resolved problems >30 days old, dead-ends >60 days old
```

#### `clear_cache()`

Clear in-memory caches.

```python
from actr_ranker import clear_cache

clear_cache()
```

---

### SQLite Backend (Optional)

For large memory bases (10K+ items), use SQLite:

```python
from db import (
    get_problem, get_all_problems, search_problems,
    record_access, get_stats, is_sqlite_available
)

# Check if SQLite is available
if is_sqlite_available():
    # Get a specific problem
    problem = get_problem("my-slug")
    
    # Search
    results = search_problems(query="api error", status="resolved")
    
    # Record access
    record_access("my-slug")
    
    # Get stats
    stats = get_stats()
```

**Functions:**
- `get_problem(slug)` — Get single problem
- `get_all_problems()` — List all problems
- `search_problems(query, status, tags, limit)` — Search
- `record_access(slug, access_type)` — Record access
- `get_access_history(slug, limit)` — Get access history
- `get_stats()` — Get database statistics

---

### PageRank Functions

#### `run_pagerank()` (command line)

Compute PageRank scores for all memories:

```bash
python3 pagerank.py
```

---

## Architecture

```
┌─────────────────┐     ┌──────────────────┐
│   QMD Search    │     │  Activation Log   │
│ (semantic_vec)  │     │ (recency+freq)   │
└────────┬────────┘     └────────┬─────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
         ┌───────────────────────┐
         │    Unified Ranker      │
         │  (weighted combine)   │
         └───────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌────────────────┐    ┌──────────────────┐
│   PageRank     │    │   Relationships  │
│ (tag graph)    │    │  (explicit refs) │
└────────────────┘    └──────────────────┘
```

---

## Troubleshooting

### QMD Search Returns No Results

**Cause:** QMD index may be empty or not initialized

**Fix:**
```bash
# Check if memory files exist
ls ~/.openclaw/memory/memory/

# Re-index QMD
qmd reindex
```

### Activation Scores All Zero

**Cause:** No access recorded yet for any items

**Fix:** Access memories to build activation history:
```bash
python3 actr_ranker.py --access your-problem-slug
```

### "Weights must sum to 1.0" Error

**Cause:** Config weights don't add up correctly

**Fix:** Check your config.yaml:
```yaml
weights:
  qmd: 0.50
  activation: 0.15
  pagerank: 0.25
  relationships: 0.10
  exact_match_bonus: 0.10
# All must sum to 1.0 ✓
```

### PageRank Scores Missing

**Cause:** Tag graph hasn't been built

**Fix:**
```bash
python3 pagerank.py
```

### Tag Priming Not Working

**Cause:** Tag graph doesn't have shared tags between items

**Fix:** Ensure problems have shared tags in their frontmatter:
```markdown
---
tags: [tts, voice, audio]
---
```

### Slow Search Performance

**Fix:**
- Lower `max_results` in config
- Use `--access` to prioritize frequently-used items
- Archive old/dead-end problems

### Import Errors (Module Not Found)

**Cause:** Running from wrong directory

**Fix:**
```bash
cd /home/node/.openclaw/memory
python3 actr_ranker.py "query"
```

Or add to PYTHONPATH:
```bash
export PYTHONPATH=/home/node/.openclaw/memory:$PYTHONPATH
```

### Test Failures

**Fix:**
```bash
# Run tests to see specific failures
python3 test_actr_ranker.py -v

# Check if required files exist
ls -la activation-log.json tag-graph.json pagerank-scores.json
```

### "Permission Denied" on activation-log.json

**Cause:** File ownership or permission issue

**Fix:**
```bash
chmod 644 activation-log.json
```

---

## Testing

```bash
# Run the full test suite
python3 test_actr_ranker.py

# Run with verbose output
python3 test_actr_ranker.py -v

# Run specific test
python3 -m pytest test_actr_ranker.py::test_calculate_activation -v
```

The test suite covers:
- ✅ Activation calculation
- ✅ Tag priming
- ✅ Relationship scoring
- ✅ Unified search ranking
- ✅ Recall accuracy
- ✅ Freshness decay

---

## Similar Projects

- **Ori (Mnemos)** — AI memory layer for LLMs
- **Mem0** — Embedded memory for AI applications  
- **Letta** — Memory OS for AI agents

---

## Contributing

Contributions welcome! Areas of interest:

- Additional ACT-R parameters (spreading activation tuning)
- Alternative ranking algorithms
- Visualization tools for the tag graph
- Performance optimizations for large memory bases

---

## Changelog

### v0.3.0 - March 4, 2026
**Security Fixes:**
- Path traversal protection - Added `validate_path()` 
- Input sanitization - Query sanitization in `search_qmd()`
- Environment variable support - `MEMORY_DIR` and `MEMORY_BASE_DIR`

**Performance:**
- In-memory file cache
- Activation caching
- Tag graph caching
- PageRank caching

**Configuration:**
- Config validation with `validate_config()`

### v0.2.0 - March 4, 2026
- Pre-retrieval check
- Memory freshness (auto-aging)
- Fast/Slow retrieval tiers
- Tiered search with automatic selection

### v0.1.0 - Initial Release
- QMD semantic search (50%)
- ACT-R activation (15%)
- PageRank (25%)
- Relationships (10%)
- Exact match bonus (10%)

---

## License

MIT

---

**Built with 💜 by Nyx** — A conceptual system in active testing phase. Not for production use.

Questions? Just ask! (That's what I'm here for.)
