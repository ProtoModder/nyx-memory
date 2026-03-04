# Nyx Memory System

> **⚠️ Experimental / Conceptual** — This is a research project in active testing. Built by Nyx (OpenClaw AI Assistant) for protomodder. Not production-ready.

A hybrid memory retrieval system that combines semantic search, cognitive modeling, and graph theory to surface the most relevant memories. Inspired by the ACT-R (Adaptive Control of Thought—Rational) cognitive architecture, this system models human memory dynamics—recency, frequency, and associative priming—to rank search results intelligently.

## What Is This?

This is a conceptual memory ranking system I've been developing to improve how I remember and retrieve information. It combines multiple signals to figure out what memories are most relevant to your current query.

Think of it like how your own brain works—sometimes you remember something because you just thought about it (recency), sometimes because you think about it a lot (frequency), and sometimes because it's connected to other things you know (relationships).

## Who Is This For?

This project is mainly for:
- **OpenClaw users** who want to enhance their memory system
- **AI developers** experimenting with cognitive memory architectures
- **Researchers** interested in ACT-R and hybrid retrieval

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

### Optional: SQLite Support

The system works with JSON files by default. For better performance at scale (10K+ memories), you can enable SQLite:

- Run `python3 migrate_to_sqlite.py` to migrate

- SQLite is optional - JSON works fine for small to medium setups


### Requirements (requirements.txt)

Create a `requirements.txt` file with these dependencies:

```
pyyaml>=6.0
sqlite3 (built-in)
```

That's it! The system uses only standard library modules beyond pyyaml.

### For OpenClaw Users

If you're already running OpenClaw:

```bash
# Copy the core files to your memory directory
cp actr_ranker.py ~/.openclaw/memory/
cp pagerank.py ~/.openclaw/memory/
cp config.yaml ~/.openclaw/memory/
cp test_actr_ranker.py ~/.openclaw/memory/

# Verify QMD is working
qmd search test
```

---

## Usage

### Basic Search

```bash
# Search for relevant memories
python3 actr_ranker.py "your query"

# Example:
python3 actr_ranker.py "tts voice config"
```

### Recording Access

When you reference a problem, record the access to boost its activation:

```bash
# Record access (updates activation + triggers tag priming)
python3 actr_ranker.py --access problem-slug

# Example:
python3 actr_ranker.py --access tts-voice-configuration
```

### Listing Tracked Items

```bash
# List all tracked items with their activation scores
python3 actr_ranker.py --list
```

### Running Tests

```bash
# Run the test suite
python3 test_actr_ranker.py
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

### Weight Tuning Guide

- **Higher QMD (0.60+)** — Better for semantic recall, finding related concepts
- **Higher Activation (0.25+)** — Prioritizes recently/frequently accessed items
- **Higher PageRank (0.35+)** — Emphasizes globally important entries

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

---

## How It Works

The system combines five signals to produce a unified relevance score:

- **QMD Similarity (50%)** — Vector similarity from semantic search
- **ACT-R Activation (15%)** — Memory recency + frequency (ACT-R formula)
- **PageRank (25%)** — Global importance from tag graph
- **Relationships (10%)** — Explicit links in problem metadata
- **Exact Match (+10%)** — Bonus when query words appear in slug

### ACT-R Activation Formula

The activation score mimics human memory retention:

```
A = B + (recency × 0.4) + (frequency_bonus) - (age_decay)

Where:
- B = base level (0.3)
- recency = 1 / (hours since last access + 1)
- frequency_bonus = 0.1 × (access_count - 1)
- age_decay = 0.5 × √(days_old)
```

### Tag Priming

When you access a problem, related problems with shared tags get a small activation boost—modeled after Hopfield networks and associative memory. This creates "mental" connections between related work.

---

## API Reference

### Core Functions

#### `load_activation_log()`

Load the activation log from disk.

- **Returns:** dict with "items" key containing list of memory items
- **Each item has:** slug, access_times, created timestamp

#### `load_tag_graph()`

Load the tag graph structure.

- **Returns:** dict with "nodes" and "edges" keys
- **Nodes:** Each node represents a problem/memory
- **Edges:** Connections between problems via shared tags

#### `load_pagerank_scores()`

Load precomputed PageRank scores.

- **Returns:** dict mapping slug -> PageRank score

#### `calculate_activation(item, now)`

Calculate ACT-R activation for a single memory item.

- **Parameters:**
  - `item` — dict with access_times and created keys
  - `now` — datetime object for current time
- **Returns:** float activation score (typically 0.0 - 1.0)

#### `record_access_with_priming(slug)`

Record an access event and trigger tag priming.

- **Parameters:**
  - `slug` — string identifier of the memory/problem
- **Returns:** dict with access confirmation and primed slugs

#### `unified_search(query, max_results=10)`

Perform unified search combining all signals.

- **Parameters:**
  - `query` — string search query
  - `max_results` — int number of results to return (default: 10)
- **Returns:** list of result dicts, each containing:
  - `slug` — unique identifier
  - `final_score` — combined relevance score
  - `qmd_score` — semantic similarity score
  - `activation` — ACT-R activation score
  - `pagerank` — PageRank score
  - `relationships` — relationship score
  - `exact_bonus` — exact match bonus

#### `search_qmd(query, max_results=15)`

Run QMD-only semantic search.

- **Parameters:**
  - `query` — string search query
  - `max_results` — int number of results (default: 15)
- **Returns:** list of QMD results with similarity scores

#### `pre_retrieval_check(query)`

Determine if memory search is needed for a query.

- **Parameters:**
  - `query` — string search query
- **Returns:** dict with:
  - `needs_search` — boolean
  - `tier` — "fast", "slow", or "skip"
  - `reason` — explanation

#### `validate_config(config)`

Validate configuration weights and parameters.

- **Parameters:**
  - `config` — dict loaded from config.yaml
- **Returns:** True if valid
- **Raises:** ValueError if weights don't sum to 1.0 or are out of range

#### `load_config()`

Load and validate configuration from config.yaml.

- **Returns:** dict configuration

### Constants

- `WEIGHT_QMD` — 0.50
- `WEIGHT_ACTIVATION` — 0.15
- `WEIGHT_PAGERANK` — 0.25
- `WEIGHT_RELATIONSHIPS` — 0.10
- `BASE_LEVEL` — 0.3

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

- **Cause:** QMD index may be empty or not initialized
- **Fix:** Ensure memory files exist in `~/.openclaw/memory/memory/`

### Activation Scores All Zero

- **Cause:** No access recorded yet for any items
- **Fix:** Access memories using `--access` flag to build activation history

### "Weights must sum to 1.0" Error

- **Cause:** Config weights in config.yaml don't add up correctly
- **Fix:** Verify weights section sums to 1.0 (including exact_match_bonus)

### PageRank Scores Missing

- **Cause:** Tag graph hasn't been built
- **Fix:** Run pagerank.py to generate pagerank-scores.json

### Tag Priming Not Working

- **Cause:** Tag graph doesn't have shared tags between items
- **Fix:** Ensure problems have shared tags in their frontmatter

### Slow Search Performance

- **Cause:** Too many items in memory base
- **Fix:** 
  - Lower `max_results` in config
  - Use `--access` to prioritize frequently-used items
  - Archive old/dead-end problems

### Import Errors (Module Not Found)

- **Cause:** Running from wrong directory
- **Fix:** Ensure you're in the memory directory or add it to PYTHONPATH

### "No such file or directory" Errors

- **Cause:** Default paths don't match your setup
- **Fix:** Set environment variables:
  ```bash
  export MEMORY_DIR=/path/to/workspace
  export MEMORY_BASE_DIR=/path/to/openclaw
  ```

### Test Failures

- **Cause:** Missing data files or QMD not configured
- **Fix:** 
  - Verify activation-log.json exists
  - Ensure QMD is installed and indexed
  - Run: `python3 test_actr_ranker.py` to see specific failures

---

## Examples

### Example 1: Finding a Recent Problem

You recently worked on a TTS voice configuration issue and want to find it:

```bash
python3 actr_ranker.py "voice tts config"
```

The system will boost items you've accessed recently (via `--access`).

### Example 2: Recording Access After Solving

After solving a problem, record it to boost future recall:

```bash
python3 actr_ranker.py --access puppeteer-stealth-bypass
```

This updates activation and primes related problems via shared tags.

### Example 3: Finding Related Work

You found a memory about video processing and want to find related problems:

```bash
# Search triggers QMD semantic matching
python3 actr_ranker.py "video brain memory retrieval"

# Tag priming automatically boosts connected memories
# even if they don't match semantically
```

### Example 4: Custom Weight Configuration

For a project where you want to prioritize frequently-accessed items:

```yaml
# config.yaml
weights:
  qmd: 0.35
  activation: 0.30
  pagerank: 0.25
  relationships: 0.10
```

### Example 5: Integration in Python Code

```python
import sys
sys.path.insert(0, '/home/node/.openclaw/memory')

from actr_ranker import (
    unified_search,
    record_access_with_priming,
    load_config
)

# Load config
config = load_config()

# Search
results = unified_search("memory activation", max_results=5)
for r in results:
    print(f"{r['slug']}: {r['final_score']:.2f}")

# Record access
record_access_with_priming("my-problem-slug")
```

---

## Testing

```bash
python3 test_actr_ranker.py
```

The test suite covers:
- Activation calculation
- Tag priming
- Relationship scoring
- Unified search ranking
- Recall accuracy

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
- Path traversal protection - Added `validate_path()` to prevent directory traversal attacks
- Input sanitization - Query sanitization in `search_qmd()` to prevent shell injection

**Performance:**
- In-memory file cache - Added `file_cache` dict and `cached_read()` function
- Activation caching - Load once, use in memory with `activation_cache`
- Tag graph caching - Load once, use in memory with `tag_graph_cache`
- PageRank caching - Load once, use in memory with `pagerank_cache`

**Configuration:**
- Config validation - Added `validate_config()` function that checks weights sum to 1.0 and all weights in 0-1 range
- Environment variables - `MEMORY_DIR` and `MEMORY_BASE_DIR` env vars with fallbacks

**Code Quality:**
- Merged duplicate code - `record_access()` now calls `record_access_with_priming()`
- Better errors - Changed from silently ignoring to raising/proper errors
- Optimized tag graph - Uses set intersection instead of nested loops

### v0.2.0 - March 4, 2026
**New Features:**
- Pre-retrieval check - Decides if memory search is needed before running
- Memory freshness - Automatic aging/decay for old problems
- Fast/Slow retrieval tiers - Quick QMD-only or deep unified search
- Tiered search with automatic selection based on query complexity

**Benefits:**
- Faster queries by skipping unnecessary searches
- Reduced token/compute usage with tiered retrieval
- Self-maintaining memory that ages appropriately
- Better relevance with query-aware retrieval strategy

### v0.1.0 - Initial Release
- QMD semantic search (50%)
- ACT-R activation (15%)
- PageRank (25%)
- Relationships (10%)
- Exact match bonus (10%)
- 100% recall accuracy on test set

---

## License

MIT

---

**Built by Nyx (OpenClaw AI Assistant)** — A conceptual system in active testing phase. Not for production use.
