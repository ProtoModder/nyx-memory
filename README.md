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

## Prerequisites

### QMD Setup Required

This system is designed to work with **QMD (Query-Managed Display)** which is part of OpenClaw's memory infrastructure. You'll need:

1. **QMD installed** on your OpenClaw instance
2. **Memory files** indexed in your memory directory
3. **Python 3** with `pyyaml` installed

To check if QMD is working:
```bash
qmd search test
```

If QMD isn't set up, check the [OpenClaw docs](https://docs.openclaw.ai) for instructions.

## Installation

Clone this repo and install dependencies:

```bash
git clone https://github.com/ProtoModder/nyx-memory.git
cd nyx-memory
pip install pyyaml
```

## For OpenClaw Users

To use this system in parallel with your existing OpenClaw memory:

### 1. Copy the files to your memory directory

```bash
cp actr_ranker.py ~/.openclaw/memory/
cp pagerank.py ~/.openclaw/memory/
cp config.yaml ~/.openclaw/memory/
cp test_actr_ranker.py ~/.openclaw/memory/
```

### 2. Build your initial graph

The system needs a tag graph to work. If you have memory files already, you'll need to build the graph structure. This is an optional step for advanced users.

### 3. Run alongside QMD

The system is designed to work *alongside* QMD, not replace it:

```bash
# Your normal QMD search still works
qmd search "your query"

# This system adds additional ranking signals
python3 actr_ranker.py "your query"
```

### 4. Integration options

You can call it from within OpenClaw by adding a tool definition. Check the examples folder (coming soon).

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
