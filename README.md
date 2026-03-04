# Nyx Memory System

> **⚠️ Experimental / Conceptual** — This is a research project in active testing. Built by Nyx (OpenClaw AI Assistant) for protomodder. Not production-ready.

A hybrid memory retrieval system that combines semantic search, cognitive modeling, and graph theory to surface the most relevant memories. Inspired by the ACT-R (Adaptive Control of Thought—Rational) cognitive architecture, this system models human memory dynamics—recency, frequency, and associative priming—to rank search results intelligently.

## Features

- **QMD Semantic Search** — Vector-based similarity matching across your knowledge base
- **ACT-R Activation** — Human memory-inspired scoring based on recency and access frequency
- **PageRank** — Graph centrality that highlights globally important entries
- **Relationships** — Explicit manual links between related problems
- **Exact Match Bonus** — Boosts results when query terms appear in the slug

## How It Works

The system combines five signals to produce a unified relevance score:

- **QMD Similarity (50%)** — Vector similarity from semantic search
- **ACT-R Activation (15%)** — Memory recency + frequency (ACT-R formula)
- **PageRank (25%)** — Global importance from tag graph
- **Relationships (10%)** — Explicit links in problem metadata
- **Exact Match (+10%)** — Bonus when query words appear in slug |

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

## Installation

```bash
pip install pyyaml
```

## Usage

```bash
# Search for relevant memories
python3 actr_ranker.py "your query"

# Record access (updates activation + triggers tag priming)
python3 actr_ranker.py --access problem-slug

# List all tracked items with their activation scores
python3 actr_ranker.py --list
```

## Configuration

Edit `config.yaml` to tune the system:

```yaml
weights:
  qmd: 0.50
  activation: 0.15
  pagerank: 0.25
  relationships: 0.10

actr:
  base_level: 0.3
  decay_constant: 0.5
  spreading_strength: 0.2
```

### When to Adjust Weights

- **Higher QMD (0.60+)** — Better for semantic recall, finding related concepts
- **Higher Activation (0.25+)** — Prioritizes recently/frequently accessed items
- **Higher PageRank (0.35+)** — Emphasizes globally important entries

## Architecture

```
┌─────────────────┐     ┌──────────────────┐
│   QMD Search    │     │  Activation Log  │
│ (semantic_vec)  │     │ (recency+freq)   │
└────────┬────────┘     └────────┬─────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
         ┌───────────────────────┐
         │    Unified Ranker     │
         │  (weighted combine)    │
         └───────────┬───────────┘
                     │
         ┌───────────┴───────────┐
         ▼                       ▼
┌────────────────┐    ┌──────────────────┐
│   PageRank     │    │   Relationships  │
│ (tag graph)    │    │  (explicit refs) │
└────────────────┘    └──────────────────┘
```

### Data Files

- `activation-log.json` — Tracks access times, frequency, and computed activation
- `tag-graph.json` — Nodes and edges from shared tags (built by separate process)
- `pagerank-scores.json` — Global importance scores computed from tag graph
- `relationships.json` — Explicit relationship mappings

## Testing

```bash
python3 test_actr_ranker.py
```

The test suite covers activation calculation, tag priming, relationship scoring, and unified search ranking.

## Similar Projects

- **Ori (Mnemos)** — AI memory layer for LLMs
- **Mem0** — Embedded memory for AI applications
- **Letta** — Memory OS for AI agents

## Contributing

Contributions welcome! Areas of interest:

- Additional ACT-R parameters (spreading activation tuning)
- Alternative ranking algorithms
- Visualization tools for the tag graph
- Performance optimizations for large memory bases

## License

MIT

---

**Built by Nyx (OpenClaw AI Assistant)** — A conceptual system in active testing phase. Not for production use.
