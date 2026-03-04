#!/usr/bin/env python3
"""
Memory Visualization Module

ASCII-based visualizations for Nyx Memory System:
- Tag cloud (show most common tags)
- Relationship graph (ASCII nodes/edges)
- Activation timeline (recently accessed)
- Memory health dashboard

Usage:
  python visualize.py --dashboard    # Show health dashboard
  python visualize.py --tags        # Show tag cloud
  python visualize.py --graph       # Show relationship graph
  python visualize.py --timeline   # Show activation timeline
  python visualize.py --all        # Show all visualizations

Or import functions:
  from visualize import show_dashboard, show_tag_cloud, show_relationship_graph, show_activation_timeline
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

# ============================================================================
# ANSI COLORS
# ============================================================================
RESET = "\033[0m"
BOLD = "\033[1m"

GREEN = "\033[92m"      # Success, high scores
YELLOW = "\033[93m"     # Warnings, medium scores
RED = "\033[91m"        # Errors, low scores
BLUE = "\033[94m"       # Headers, info
CYAN = "\033[96m"       # Highlights
GRAY = "\033[90m"       # Muted text


def colorize(text, color):
    """Apply ANSI color to text."""
    return f"{color}{text}{RESET}"


def success(text):
    """Green text for success messages."""
    return colorize(text, GREEN)


def warning(text):
    """Yellow text for warnings."""
    return colorize(text, YELLOW)


def error(text):
    """Red text for errors."""
    return colorize(text, RED)


def header(text):
    """Blue bold text for headers."""
    return colorize(f"{BOLD}{text}", BLUE)


def highlight(text):
    """Cyan text for highlights."""
    return colorize(text, CYAN)


def muted(text):
    """Gray text for muted info."""
    return colorize(text, GRAY)


# ============================================================================
# DATA LOADING
# ============================================================================

MEMORY_DIR = Path(os.environ.get("MEMORY_DIR", "/home/node/.openclaw/workspace"))
MEMORY_BASE_DIR = Path(os.environ.get("MEMORY_BASE_DIR", "/home/node/.openclaw"))

ACTIVATION_LOG = MEMORY_BASE_DIR / "memory/activation-log.json"
TAG_GRAPH_PATH = MEMORY_BASE_DIR / "memory/tag-graph.json"
PAGERANK_SCORES_PATH = MEMORY_BASE_DIR / "memory/pagerank-scores.json"

activation_cache = None
tag_graph_cache = None
pagerank_cache = None


def load_activation_log(force_reload=False):
    """Load the activation log with caching."""
    global activation_cache
    
    if activation_cache is not None and not force_reload:
        return activation_cache
    
    try:
        if ACTIVATION_LOG.exists():
            with open(ACTIVATION_LOG) as f:
                activation_cache = json.load(f)
                return activation_cache
    except Exception as e:
        print(f"ERROR: Could not load activation-log: {e}")
    
    activation_cache = {"version": "1.0", "last_updated": None, "items": {}}
    return activation_cache


def load_tag_graph(force_reload=False):
    """Load the tag graph with caching."""
    global tag_graph_cache
    
    if tag_graph_cache is not None and not force_reload:
        return tag_graph_cache
    
    if TAG_GRAPH_PATH.exists():
        try:
            with open(TAG_GRAPH_PATH) as f:
                tag_graph_cache = json.load(f)
                return tag_graph_cache
        except Exception as e:
            print(f"ERROR: Could not load tag-graph: {e}")
    
    tag_graph_cache = {"nodes": {}, "edges": [], "tag_index": {}}
    return tag_graph_cache


def load_pagerank_scores(force_reload=False):
    """Load PageRank scores with caching."""
    global pagerank_cache
    
    if pagerank_cache is not None and not force_reload:
        return pagerank_cache
    
    try:
        if PAGERANK_SCORES_PATH.exists():
            with open(PAGERANK_SCORES_PATH) as f:
                data = json.load(f)
                pagerank_cache = data.get("scores", {})
                return pagerank_cache
    except Exception as e:
        print(f"ERROR: Could not load pagerank-scores: {e}")
    
    pagerank_cache = {}
    return pagerank_cache


def load_tags_from_file(path):
    """Load tags from a problem markdown file."""
    full_path = MEMORY_DIR / path
    if not full_path.exists():
        return []
    
    try:
        content = full_path.read_text()
        for line in content.split('\n'):
            line = line.strip()
            if line.startswith('**Tags:**'):
                tags_str = line.replace('**Tags:**', '').strip()
                if tags_str:
                    return [t.strip().rstrip(',') for t in tags_str.split() if t.strip()]
    except Exception:
        pass
    
    return []


# ============================================================================
# CALCULATION HELPERS
# ============================================================================

BASE_LEVEL = 0.3
DECAY_CONSTANT = 0.5


def calculate_activation(item_data, current_time):
    """Calculate ACT-R style activation."""
    access_times = item_data.get("access_times", [])
    if not access_times:
        return BASE_LEVEL
    
    try:
        last_access = datetime.fromisoformat(access_times[-1].replace("Z", "+00:00"))
        seconds_ago = (current_time - last_access).total_seconds()
        recency = 1.0 / ((seconds_ago / 3600) + 1)
        
        frequency = len(access_times)
        frequency_bonus = 0.1 * (frequency - 1)
        
        age = (current_time - datetime.fromisoformat(
            item_data["created"].replace("Z", "+00:00")
        )).total_seconds() / 86400
        
        decay = DECAY_CONSTANT * (age ** 0.5)
        
        activation = BASE_LEVEL + recency * 0.4 + frequency_bonus - decay
        return max(0.0, min(1.0, activation))
    except Exception:
        return BASE_LEVEL


# ============================================================================
# VISUALIZATION FUNCTIONS
# ============================================================================

def get_all_tags():
    """Extract all tags from activation log and tag graph."""
    tag_counts = {}
    
    data = load_activation_log()
    for slug, item in data.get("items", {}).items():
        tags = item.get("tags", [])
        if not tags:
            path = item.get("path", f"memory/problems/{slug}.md")
            tags = load_tags_from_file(path)
            if tags:
                item["tags"] = tags
        for tag in tags:
            tag_counts[tag] = tag_counts.get(tag, 0) + 1
    
    tag_graph = load_tag_graph()
    for tag, node_data in tag_graph.get("nodes", {}).items():
        if tag not in tag_counts:
            tag_counts[tag] = node_data.get("count", 1)
    
    return tag_counts


def show_tag_cloud(max_tags=15):
    """
    Display a tag cloud showing most common tags.
    
    Args:
        max_tags: Maximum number of tags to display (default 15)
    """
    tag_counts = get_all_tags()
    
    if not tag_counts:
        print(f"{warning('No tags found in memory')}")
        return
    
    sorted_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:max_tags]
    max_count = max(count for _, count in sorted_tags) if sorted_tags else 1
    
    # ANSI colors for tag cloud gradient
    tag_colors = [
        "\033[38;5;196m",  # Red
        "\033[38;5;202m",  # Orange-Red
        "\033[38;5;208m",  # Orange
        "\033[38;5;214m",  # Gold
        "\033[38;5;220m",  # Yellow
        "\033[38;5;228m",  # Light Yellow
        "\033[38;5;15m",   # White
    ]
    
    print(f"\n{header('═' * 50)}")
    print(f"{header('  TAG CLOUD')} {muted(f'(top {len(sorted_tags)} tags)')}")
    print(f"{header('═' * 50)}\n")
    
    for tag, count in sorted_tags:
        scale = count / max_count
        color_idx = int(scale * (len(tag_colors) - 1))
        color = tag_colors[color_idx]
        
        if scale > 0.8:
            size_indicator = "●●●"
        elif scale > 0.5:
            size_indicator = "●●○"
        elif scale > 0.25:
            size_indicator = "●○○"
        else:
            size_indicator = "○○○"
        
        print(f"  {color}{tag}{RESET} ({count}) {muted(size_indicator)}")
    
    print(f"\n{muted('Key: ●●● High │ ●●○ Medium │ ●○○ Low │ ○○○ Minimal')}\n")


def show_relationship_graph(max_nodes=10, max_edges=15):
    """
    Display an ASCII relationship graph showing connections between memories.
    
    Args:
        max_nodes: Maximum number of nodes to display (default 10)
        max_edges: Maximum number of edges to display (default 15)
    """
    data = load_activation_log()
    
    if not data.get("items"):
        print(f"{warning('No items in memory')}")
        return
    
    current_time = datetime.now(timezone.utc)
    items_with_activation = []
    for slug, item in data["items"].items():
        act = calculate_activation(item, current_time)
        items_with_activation.append((slug, act, item))
    
    items_with_activation.sort(key=lambda x: x[1], reverse=True)
    top_items = items_with_activation[:max_nodes]
    
    edges_shown = 0
    
    print(f"\n{header('═' * 50)}")
    print(f"{header('  RELATIONSHIP GRAPH')}")
    print(f"{header('═' * 50)}\n")
    
    # Header row
    print("    ", end="")
    for slug, act, _ in top_items:
        short_slug = slug[:8] if len(slug) > 8 else slug
        print(highlight(short_slug.center(8)), end=" ")
    print()
    
    # Adjacency matrix
    for i, (slug_i, act_i, _) in enumerate(top_items):
        short_i = slug_i[:8] if len(slug_i) > 8 else slug_i
        print(f"  {highlight(short_i.ljust(8))}", end=" ")
        
        for j, (slug_j, act_j, _) in enumerate(top_items):
            if i == j:
                print(muted("■".center(8)), end=" ")
            else:
                item_i = data["items"].get(slug_i, {})
                item_j = data["items"].get(slug_j, {})
                tags_i = set(item_i.get("tags", []))
                tags_j = set(item_j.get("tags", []))
                
                if tags_i & tags_j:
                    strength = len(tags_i & tags_j)
                    centered = "●".center(8)
                    if strength >= 3:
                        print(success(centered), end=" ")
                    elif strength >= 2:
                        print(highlight(centered), end=" ")
                    else:
                        print(f"{YELLOW}●{RESET}    ", end=" ")
                    edges_shown += 1
                else:
                    print(muted("○".center(8)), end=" ")
        
        print()
        
        if edges_shown >= max_edges:
            break
    
    print(f"\n{muted('Legend: ■ Self │ ● Connected │ ○ No connection')}")
    print(f"{muted('Strength: ●●● Strong │ ●●○ Medium │ ●○○ Weak')}\n")


def show_activation_timeline(limit=10):
    """
    Display a timeline of recently accessed memories.
    
    Args:
        limit: Number of recent accesses to show (default 10)
    """
    data = load_activation_log()
    
    if not data.get("items"):
        print(f"{warning('No items in memory')}")
        return
    
    all_accesses = []
    current_time = datetime.now(timezone.utc)
    
    for slug, item in data["items"].items():
        access_times = item.get("access_times", [])
        access_count = item.get("access_count", len(access_times))
        
        if access_times:
            try:
                last_access = access_times[-1]
                last_dt = datetime.fromisoformat(last_access.replace("Z", "+00:00"))
                delta = current_time - last_dt
                
                if delta.days > 0:
                    relative = f"{delta.days}d ago"
                elif delta.seconds > 3600:
                    relative = f"{delta.seconds // 3600}h ago"
                elif delta.seconds > 60:
                    relative = f"{delta.seconds // 60}m ago"
                else:
                    relative = "just now"
                
                all_accesses.append({
                    "slug": slug,
                    "last_access": last_dt,
                    "relative": relative,
                    "access_count": access_count
                })
            except Exception:
                pass
    
    all_accesses.sort(key=lambda x: x["last_access"], reverse=True)
    recent = all_accesses[:limit]
    
    print(f"\n{header('═' * 50)}")
    print(f"{header('  ACTIVATION TIMELINE')} {muted(f'(recent {len(recent)})')}")
    print(f"{header('═' * 50)}\n")
    
    if not recent:
        print(f"  {warning('No access history yet')}")
        return
    
    for item in recent:
        slug = item["slug"]
        relative = item["relative"]
        count = item["access_count"]
        
        if "just now" in relative or "m ago" in relative:
            color = GREEN
            marker = "●"
        elif "h ago" in relative:
            color = CYAN
            marker = "◆"
        elif "d ago" in relative and int(relative.split("d")[0]) <= 2:
            color = YELLOW
            marker = "○"
        else:
            color = GRAY
            marker = "○"
        
        print(f"  {color}{marker}{RESET} {highlight(slug)}")
        print(f"     {muted('Last:')} {relative} {muted('│ Accesses:')} {count}")
        print()
    
    print(f"{muted('Timeline shows most recently accessed memories')}\n")


def show_dashboard():
    """
    Display a comprehensive memory health dashboard.
    """
    data = load_activation_log()
    tag_graph = load_tag_graph()
    pagerank = load_pagerank_scores()
    current_time = datetime.now(timezone.utc)
    
    total_items = len(data.get("items", {}))
    total_tags = len(tag_graph.get("nodes", {}))
    total_edges = len(tag_graph.get("edges", []))
    
    activations = []
    for slug, item in data.get("items", {}).items():
        act = calculate_activation(item, current_time)
        activations.append(act)
    
    avg_activation = sum(activations) / len(activations) if activations else 0
    high_activation = sum(1 for a in activations if a > 0.5)
    medium_activation = sum(1 for a in activations if 0.25 < a <= 0.5)
    low_activation = sum(1 for a in activations if a <= 0.25)
    
    total_accesses = sum(item.get("access_count", 0) for item in data.get("items", {}).values())
    items_never_accessed = sum(1 for item in data.get("items", {}).values() if not item.get("access_times"))
    
    # Health score
    health_score = 0
    if total_items > 0:
        health_score += min(25, total_items * 2.5)
    if total_tags > 0:
        health_score += min(20, total_tags * 2)
    if avg_activation > 0.3:
        health_score += min(25, avg_activation * 50)
    if total_accesses > 0:
        health_score += min(15, total_accesses)
    if items_never_accessed == 0:
        health_score += 15
    elif items_never_accessed < total_items * 0.2:
        health_score += 5
    
    health_score = min(100, int(health_score))
    
    if health_score >= 75:
        health_color = GREEN
        health_status = "EXCELLENT"
    elif health_score >= 50:
        health_color = CYAN
        health_status = "HEALTHY"
    elif health_score >= 25:
        health_color = YELLOW
        health_status = "FAIR"
    else:
        health_color = RED
        health_status = "NEEDS ATTENTION"
    
    print(f"\n{header('═' * 60)}")
    print(f"{header('  MEMORY HEALTH DASHBOARD')}")
    print(f"{header('═' * 60)}\n")
    
    print(f"  ┌{'─' * 30}┐")
    print(f"  │ {muted('OVERALL HEALTH:')} {health_color}{health_status}{RESET} {' ' * (16 - len(health_status))}│")
    print(f"  │ {muted('Score:')} {health_color}{health_score}%{RESET}{' ' * (30 - len(str(health_score)) - 10)}│")
    print(f"  └{'─' * 30}┘\n")
    
    print(f"  {header('📊 MEMORY STATS')}")
    print(f"  {'─' * 40}")
    print(f"  {muted('Total Memories:')}    {highlight(str(total_items))}")
    print(f"  {muted('Total Tags:')}       {highlight(str(total_tags))}")
    print(f"  {muted('Tag Connections:')} {highlight(str(total_edges))}")
    print(f"  {muted('Total Accesses:')}  {highlight(str(total_accesses))}")
    print()
    
    print(f"  {header('📈 ACTIVATION DISTRIBUTION')}")
    print(f"  {'─' * 40}")
    
    bar_width = 30
    if total_items > 0:
        high_pct = high_activation / total_items
        med_pct = medium_activation / total_items
        low_pct = low_activation / total_items
        
        high_bar = int(high_pct * bar_width)
        med_bar = int(med_pct * bar_width)
        low_bar = int(low_pct * bar_width)
        
        print(f"  {GREEN}█{RESET} {muted('High (>50%):')}    {high_bar:>2} {GREEN}{'█' * high_bar}{RESET}")
        print(f"  {YELLOW}█{RESET} {muted('Medium (25-50%):')} {med_bar:>2} {YELLOW}{'█' * med_bar}{RESET}")
        print(f"  {RED}█{RESET} {muted('Low (<25%):')}     {low_bar:>2} {RED}{'█' * low_bar}{RESET}")
    else:
        print(f"  {muted('No data available')}")
    
    print()
    
    avg_pagerank = sum(pagerank.values()) / len(pagerank) if pagerank else 0
    
    print(f"  {header('📉 AVERAGE METRICS')}")
    print(f"  {'─' * 40}")
    print(f"  {muted('Avg Activation:')}   {highlight(f'{avg_activation:.2f}')}")
    print(f"  {muted('PageRank Avg:')}    {highlight(f'{avg_pagerank:.2f}')}")
    print(f"  {muted('Never Accessed:')}  {warning(f'{items_never_accessed}')}")
    
    print(f"\n{header('═' * 60)}\n")


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        prog="visualize.py",
        description=header("Memory Visualization Tools for Nyx"),
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    
    parser.add_argument(
        "--tags", "-t",
        action="store_true",
        help="Show tag cloud"
    )
    
    parser.add_argument(
        "--graph", "-g",
        action="store_true",
        help="Show relationship graph"
    )
    
    parser.add_argument(
        "--timeline", "-l",
        action="store_true",
        help="Show activation timeline"
    )
    
    parser.add_argument(
        "--dashboard", "-d",
        action="store_true",
        help="Show memory health dashboard"
    )
    
    parser.add_argument(
        "--all", "-a",
        action="store_true",
        help="Show all visualizations"
    )
    
    args = parser.parse_args()
    
    # If no flags, show all
    if not any([args.tags, args.graph, args.timeline, args.dashboard, args.all]):
        args.all = True
    
    if args.all or args.dashboard:
        show_dashboard()
    
    if args.all or args.tags:
        show_tag_cloud()
    
    if args.all or args.timeline:
        show_activation_timeline()
    
    if args.all or args.graph:
        show_relationship_graph()


if __name__ == "__main__":
    main()
