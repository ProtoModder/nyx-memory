#!/usr/bin/env python3
"""
PageRank for Tag Graph Memory

Calculates PageRank scores for problems based on tag relationships.
Nodes = problems, Edges = shared tags between problems.
"""

import json
from datetime import datetime, timezone
from pathlib import Path
from collections import defaultdict

# Paths
MEMORY_DIR = Path("/home/node/.openclaw/memory")
TAG_GRAPH_PATH = MEMORY_DIR / "tag-graph.json"
PAGERANK_SCORES_PATH = MEMORY_DIR / "pagerank-scores.json"
ACTIVATION_LOG_PATH = MEMORY_DIR / "activation-log.json"

# PageRank parameters
DAMPING = 0.85
ITERATIONS = 20


def load_activation_log():
    """Load the activation log with problem tags."""
    if ACTIVATION_LOG_PATH.exists():
        with open(ACTIVATION_LOG_PATH) as f:
            return json.load(f)
    return {"version": "1.0", "items": {}}


def build_tag_graph():
    """
    Build a tag-based graph from activation log.
    Nodes = problems, Edges exist between problems that share tags.
    """
    data = load_activation_log()
    
    # Build tag -> set of slugs mapping
    tag_to_slugs = defaultdict(set)
    slug_to_tags = {}
    
    for slug, item in data.get("items", {}).items():
        tags = item.get("tags", [])
        slug_to_tags[slug] = set(tags)
        for tag in tags:
            tag_to_slugs[tag].add(slug)
    
    # Build adjacency list (edges between slugs that share tags)
    edges = defaultdict(set)
    
    for tag, slugs in tag_to_slugs.items():
        slug_list = list(slugs)
        for i, slug_a in enumerate(slug_list):
            for slug_b in slug_list[i+1:]:
                edges[slug_a].add(slug_b)
                edges[slug_b].add(slug_a)
    
    # Create graph in expected format
    nodes = list(slug_to_tags.keys())
    graph = {
        "nodes": [{"id": slug, "tags": list(slug_to_tags[slug])} for slug in nodes],
        "edges": [
            {"source": a, "target": b} 
            for a, targets in edges.items() 
            for b in targets
        ]
    }
    
    return graph


def load_or_build_graph():
    """Load existing tag-graph.json or build from activation log."""
    if TAG_GRAPH_PATH.exists():
        with open(TAG_GRAPH_PATH) as f:
            return json.load(f)
    else:
        graph = build_tag_graph()
        # Save for future use
        with open(TAG_GRAPH_PATH, "w") as f:
            json.dump(graph, f, indent=2)
        return graph


def compute_pagerank(graph, damping=DAMPING, iterations=ITERATIONS):
    """
    Compute PageRank on the graph.
    
    Args:
        graph: dict with 'nodes' and 'edges'
        damping: damping factor (default 0.85)
        iterations: number of iterations (default 20)
    
    Returns:
        dict mapping node id -> PageRank score
    """
    nodes = {node["id"] for node in graph.get("nodes", [])}
    n = len(nodes)
    
    if n == 0:
        return {}
    
    # Build adjacency with out-degree tracking
    out_links = defaultdict(set)
    in_links = defaultdict(set)
    
    for edge in graph.get("edges", []):
        source = edge.get("source")
        target = edge.get("target")
        if source and target and source in nodes and target in nodes:
            out_links[source].add(target)
            in_links[target].add(source)
    
    # Initialize ranks equally
    rank = {node: 1.0 / n for node in nodes}
    
    # PageRank iterations
    for _ in range(iterations):
        new_rank = {}
        
        # Teleportation constant
        teleport = (1 - damping) / n
        
        for node in nodes:
            # Sum of rank_of_neighbors / out_degree for all incoming edges
            inbound = in_links.get(node, set())
            if inbound:
                sum_ranks = sum(
                    rank[neighbor] / len(out_links.get(neighbor, set()) | {node})
                    for neighbor in inbound
                    if out_links.get(neighbor)  # Only if has outgoing links
                )
            else:
                sum_ranks = 0
            
            new_rank[node] = teleport + damping * sum_ranks
        
        rank = new_rank
    
    return rank


def save_pagerank_scores(scores, damping=DAMPING, iterations=ITERATIONS):
    """Save PageRank scores to JSON."""
    output = {
        "version": "1.0",
        "calculated": datetime.now(timezone.utc).isoformat(),
        "damping": damping,
        "iterations": iterations,
        "scores": scores
    }
    
    with open(PAGERANK_SCORES_PATH, "w") as f:
        json.dump(output, f, indent=2)
    
    return output


def get_pagerank_score(slug, scores_path=None):
    """
    Get PageRank score for a problem slug.
    
    Args:
        slug: The problem slug to look up
        scores_path: Optional custom path to scores file
    
    Returns:
        float: PageRank score, or 0.0 if not found
    """
    if scores_path is None:
        scores_path = PAGERANK_SCORES_PATH
    
    if Path(scores_path).exists():
        with open(scores_path) as f:
            data = json.load(f)
            return data.get("scores", {}).get(slug, 0.0)
    
    return 0.0


def run_pagerank():
    """Main entry point to compute and save PageRank scores."""
    print("Loading graph...")
    graph = load_or_build_graph()
    
    nodes_count = len(graph.get("nodes", []))
    edges_count = len(graph.get("edges", []))
    print(f"Graph: {nodes_count} nodes, {edges_count} edges")
    
    print(f"Computing PageRank (d={DAMPING}, iter={ITERATIONS})...")
    scores = compute_pagerank(graph, DAMPING, ITERATIONS)
    
    print(f"Saving scores to {PAGERANK_SCORES_PATH}...")
    result = save_pagerank_scores(scores, DAMPING, ITERATIONS)
    
    # Print top 10
    sorted_scores = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    print("\nTop 10 by PageRank:")
    for slug, score in sorted_scores[:10]:
        print(f"  {slug}: {score:.6f}")
    
    return result


if __name__ == "__main__":
    run_pagerank()
