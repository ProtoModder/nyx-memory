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

import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

import yaml

MEMORY_DIR = Path("/home/node/.openclaw/workspace/memory")
ACTIVATION_LOG = Path("/home/node/.openclaw/memory/activation-log.json")
TAG_GRAPH_PATH = Path("/home/node/.openclaw/memory/tag-graph.json")
PAGERANK_SCORES_PATH = Path("/home/node/.openclaw/memory/pagerank-scores.json")
CONFIG_PATH = Path(__file__).parent / "config.yaml"


def load_config():
    """Load configuration from config.yaml."""
    if CONFIG_PATH.exists():
        with open(CONFIG_PATH) as f:
            return yaml.safe_load(f)
    return {}


# Load config
_config = load_config()

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


def load_activation_log():
    """Load the activation log with error handling."""
    try:
        if ACTIVATION_LOG.exists():
            with open(ACTIVATION_LOG) as f:
                data = json.load(f)
                return data
    except json.JSONDecodeError as e:
        print(f"Warning: activation-log.json is corrupt: {e}")
    except Exception as e:
        print(f"Warning: Could not load activation-log: {e}")
    return {"version": "1.0", "last_updated": None, "items": {}}


def save_activation_log(data):
    """Save the activation log."""
    data["last_updated"] = datetime.now(timezone.utc).isoformat()
    with open(ACTIVATION_LOG, "w") as f:
        json.dump(data, f, indent=2)


def calculate_activation(item_data, current_time):
    """
    Calculate ACT-R style activation:
    A = B + Σ(Sᵢ / Dᵢ) - F
    
    Simplified: A = B + recency_score + frequency_bonus - decay
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
    decay = DECAY_CONSTANT * (age ** 0.5)
    
    activation = BASE_LEVEL + recency * 0.4 + frequency_bonus - decay
    return max(0.0, min(1.0, activation))  # Clamp to 0-1


def get_related_by_tags(slug, data):
    """Get slugs that share tags with the given slug (tag priming)."""
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
        full_path = Path("/home/node/.openclaw/workspace") / path
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


def record_access_with_priming(slug):
    """
    Record access and boost related problems that share tags.
    This is tag priming - inspired by Hopfield networks / associative memory.
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
            print(f"  🔗 Primed {related_slug}: +{boost:.3f} (shared tags: {shared_count})")
    
    save_activation_log(data)
    return data["items"][slug]["activation"]


def record_access(slug):
    """Record that a problem was accessed."""
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


def search_qmd(query, max_results=10):
    """Run QMD search and return results with error handling."""
    try:
        result = subprocess.run(
            ["qmd", "search", query],
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
                    
        return results[:max_results]
    except FileNotFoundError:
        print("Warning: qmd command not found")
        return []
    except subprocess.TimeoutExpired:
        print(f"Warning: qmd search timed out for query: {query}")
        return []
    except Exception as e:
        print(f"Warning: QMD search error: {e}")
        return []  # Graceful degradation: return empty results


def combined_search(query, max_results=5):
    """
    Legacy: Parallel pipeline: QMD + ACT-R activation
    
    Returns results ranked by: w1 * qmd_score + w2 * activation
    """
    data = load_activation_log()
    current_time = datetime.now(timezone.utc)
    
    # Get QMD results
    qmd_results = search_qmd(query, max_results=10)
    
    # Combine with activation scores
    combined = []
    for item in qmd_results:
        slug = item["slug"]
        
        if slug in data["items"]:
            activation = calculate_activation(data["items"][slug], current_time)
        else:
            activation = BASE_LEVEL
        
        # Weighted combination (60% QMD, 40% activation)
        final_score = 0.6 * item["qmd_score"] + 0.4 * activation
        
        combined.append({
            "slug": slug,
            "path": item["path"],
            "qmd_score": item["qmd_score"],
            "activation": activation,
            "final_score": final_score
        })
    
    # Sort by final score
    combined.sort(key=lambda x: x["final_score"], reverse=True)
    
    return combined[:max_results]


def load_tag_graph():
    """Load the tag graph."""
    if TAG_GRAPH_PATH.exists():
        with open(TAG_GRAPH_PATH) as f:
            return json.load(f)
    return {"nodes": {}, "edges": [], "tag_index": {}}


def load_pagerank_scores():
    """Load PageRank scores with error handling."""
    try:
        if PAGERANK_SCORES_PATH.exists():
            with open(PAGERANK_SCORES_PATH) as f:
                data = json.load(f)
                return data.get("scores", {})
    except json.JSONDecodeError as e:
        print(f"Warning: pagerank-scores.json is corrupt: {e}")
    except Exception as e:
        print(f"Warning: Could not load pagerank-scores: {e}")
    return {}


def get_relationship_score(slug, problem_path=None):
    """
    Check if problem has explicit relationships to query-related problems.
    
    Looks for ## Relationships section in problem file.
    Returns normalized score (0-1) based on number of relationships.
    """
    if problem_path is None:
        problem_path = f"memory/problems/{slug}.md"
    
    try:
        full_path = Path("/home/node/.openclaw/workspace") / problem_path
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


def unified_search(query, max_results=5):
    """
    Unified search: QMD + Activation + PageRank + Relationships
    
    Final = 0.30×QMD + 0.30×Activation + 0.25×PageRank + 0.15×Relationships
    
    Args:
        query: Search query string
        max_results: Maximum number of results to return
    
    Returns:
        List of dicts with all scores and final ranking
    """
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
    
    if len(sys.argv) < 2:
        print("Usage: actr_ranker.py <query>")
        print("       actr_ranker.py --access <slug>")
        print("       actr_ranker.py --list")
        sys.exit(1)
    
    if sys.argv[1] == "--access":
        slug = sys.argv[2]
        print(f"Recording access for {slug} (with tag priming)...")
        activation = record_access_with_priming(slug)
        print(f"Recorded access for {slug}, activation: {activation:.3f}")
    
    elif sys.argv[1] == "--list":
        data = load_activation_log()
        current_time = datetime.now(timezone.utc)
        for slug, item in data["items"].items():
            act = calculate_activation(item, current_time)
            print(f"{slug}: activation={act:.3f}, accesses={item['access_count']}")
    
    else:
        query = " ".join(sys.argv[1:])
        results = unified_search(query)
        
        print(f"\n=== Unified Search: '{query}' ===\n")
        print(f"Weights: QMD={WEIGHT_QMD} | Activation={WEIGHT_ACTIVATION} | PageRank={WEIGHT_PAGERANK} | Relationships={WEIGHT_RELATIONSHIPS}\n")
        
        for i, r in enumerate(results, 1):
            print(f"{i}. {r['slug']}")
            print(f"   QMD: {r['qmd_score']:.2f} | Activation: {r['activation']:.2f} | PageRank: {r['pagerank']:.2f} | Relationships: {r['relationship_score']:.2f} | Final: {r['final_score']:.2f}")
            print(f"   Path: {r['path']}")
            print()


if __name__ == "__main__":
    main()
