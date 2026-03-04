#!/usr/bin/env python3
"""
Memory Visualization Module

ASCII-based visualizations for Nyx Memory System:
- Tag cloud (show most common tags)
- Relationship graph (ASCII nodes/edges)
- Activation timeline (recently accessed)
- Memory health dashboard
- Sparkline charts
- Heatmaps

Usage:
  python visualize.py --dashboard    # Show health dashboard
  python visualize.py --tags        # Show tag cloud
  python visualize.py --graph       # Show relationship graph
  python visualize.py --timeline   # Show activation timeline
  python visualize.py --all        # Show all visualizations

Or import functions:
  from visualize import show_dashboard, show_tag_cloud, show_relationship_graph, show_activation_timeline
"""

from datetime import datetime, timezone
from pathlib import Path

# Import shared utilities
from memory_utils import (
    load_activation_log,
    load_tag_graph,
    load_pagerank_scores,
    load_tags_from_file,
    calculate_activation,
    BASE_LEVEL,
    DECAY_CONSTANT,
    # ANSI colors
    colorize,
    success,
    warning,
    error,
    header,
    highlight,
    muted,
    RESET,
    BOLD,
    GREEN,
    YELLOW,
    RED,
    BLUE,
    CYAN,
    GRAY,
)

# ============================================================================
# EXTENDED COLOR PALETTE (ANSI 256 colors)
# ============================================================================

# Gradient palettes for different visualizations
TAG_CLOUD_PALETTE = [
    "\033[38;5;196m",  # Red
    "\033[38;5;199m",  # Pink
    "\033[38;5;201m",  # Hot pink
    "\033[38;5;205m",  # Light pink
    "\033[38;5;207m",  # Pink
    "\033[38;5;219m",  # Light magenta
    "\033[38;5;225m",  # Very light pink
    "\033[38;5;231m",  # White
]

ACTIVATION_PALETTE = [
    "\033[38;5;196m",  # Red (cold)
    "\033[38;5;202m",  # Orange-red
    "\033[38;5;208m",  # Orange
    "\033[38;5;214m",  # Gold
    "\033[38;5;220m",  # Yellow
    "\033[38;5;154m",  # Lime
    "\033[38;5;118m",  # Green
    "\033[38;5;35m",   # Dark green (hot)
]

SPARKLINE_PALETTE = [
    "\033[38;5;239m",  # Dark gray
    "\033[38;5;245m",  # Gray
    "\033[38;5;250m",  # Light gray
    "\033[38;5;255m",  # Near white
]

# Box drawing characters
BOX_TL = "╭"
BOX_TR = "╮"
BOX_BL = "╰"
BOX_BR = "╯"
BOX_H = "─"
BOX_V = "│"

# ============================================================================
# VISUALIZATION HELPERS
# ============================================================================

def get_gradient_color(value, palette):
    """Get color from gradient palette based on normalized value (0-1)."""
    idx = min(int(value * (len(palette) - 1)), len(palette) - 1)
    return palette[idx]


def color_bar(value, width=10, palette=None):
    """Create a colored bar chart segment."""
    if palette is None:
        palette = ACTIVATION_PALETTE
    fill_count = int(value * width)
    empty_count = width - fill_count
    color = get_gradient_color(value, palette)
    return f"{color}{'█' * fill_count}{GRAY}{'░' * empty_count}{RESET}"


def sparkline(values, width=20, palette=None):
    """Generate a colored ASCII sparkline."""
    if not values or len(values) < 2:
        return muted("─" * width)
    
    if palette is None:
        palette = SPARKLINE_PALETTE
    
    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val if max_val != min_val else 1
    
    result = []
    for v in values:
        normalized = (v - min_val) / range_val
        color = get_gradient_color(normalized, palette)
        if normalized > 0.75:
            char = "▄"
        elif normalized > 0.5:
            char = "▃"
        elif normalized > 0.25:
            char = "▂"
        else:
            char = "▁"
        result.append(f"{color}{char}{RESET}")
    
    return "".join(result)


def horizontal_rule(char=BOX_H, length=50):
    """Create a horizontal rule."""
    return header(char * length)


def format_percentage(value, decimals=1):
    """Format a value as a percentage."""
    return f"{value * 100:.{decimals}f}%"


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
    
    print(f"\n{horizontal_rule()}")
    print(f"{header('  TAG CLOUD')} {muted(f'(top {len(sorted_tags)} tags)')}")
    print(f"{horizontal_rule()}\n")
    
    # Group tags by intensity for better visual grouping
    high_tags = [(t, c) for t, c in sorted_tags if c / max_count > 0.6]
    med_tags = [(t, c) for t, c in sorted_tags if 0.3 < c / max_count <= 0.6]
    low_tags = [(t, c) for t, c in sorted_tags if c / max_count <= 0.3]
    
    # High intensity
    for tag, count in high_tags:
        scale = count / max_count
        color = get_gradient_color(scale, TAG_CLOUD_PALETTE)
        size_indicator = "●●●"
        print(f"  {color}{BOLD}{tag}{RESET} {highlight(f'({count})')} {muted(size_indicator)}")
    
    if med_tags:
        print()
        for tag, count in med_tags:
            scale = count / max_count
            color = get_gradient_color(scale, TAG_CLOUD_PALETTE)
            size_indicator = "●●○"
            print(f"  {color}{tag}{RESET} ({count}) {muted(size_indicator)}")
    
    if low_tags:
        print()
        for tag, count in low_tags:
            scale = count / max_count
            color = get_gradient_color(scale, TAG_CLOUD_PALETTE)
            size_indicator = "●○○"
            print(f"  {muted(tag)} ({count}) {muted(size_indicator)}")
    
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
    
    print(f"\n{horizontal_rule()}")
    print(f"{header('  RELATIONSHIP GRAPH')}")
    print(f"{horizontal_rule()}\n")
    
    # Header row with activation indicators
    print(f"  {muted('Node')}", end="")
    for slug, act, _ in top_items:
        short_slug = slug[:6] if len(slug) > 6 else slug
        act_indicator = "●" if act > 0.5 else "○"
        act_color = GREEN if act > 0.5 else GRAY
        print(f" {colorize(short_slug[:5].center(5), act_color)}", end="")
    print()
    
    # Divider with legend
    print(f"  {muted('-' * 6)}", end="")
    for _ in top_items:
        print(f" {muted(BOX_H * 5)}", end="")
    print()
    
    # Adjacency matrix with better visualization
    edge_count = 0
    for i, (slug_i, act_i, _) in enumerate(top_items):
        short_i = slug_i[:6] if len(slug_i) > 6 else slug_i
        act_indicator = "●" if act_i > 0.5 else "○"
        act_color = GREEN if act_i > 0.5 else GRAY
        
        print(f"  {colorize(short_i[:5].ljust(5), act_color)} ", end="")
        
        for j, (slug_j, act_j, _) in enumerate(top_items):
            if i == j:
                print(f"{muted('■')}", end=" ")
            else:
                item_i = data["items"].get(slug_i, {})
                item_j = data["items"].get(slug_j, {})
                tags_i = set(item_i.get("tags", []))
                tags_j = set(item_j.get("tags", []))
                
                shared = tags_i & tags_j
                if shared:
                    strength = len(shared)
                    if strength >= 3:
                        print(f"{success('●')}", end=" ")
                    elif strength >= 2:
                        print(f"{highlight('●')}", end=" ")
                    else:
                        print(f"{colorize('●', '\033[38;5;214m')}", end=" ")
                    edge_count += 1
                else:
                    print(f"{muted('·')}", end=" ")
        
        print()
        
        if edge_count >= max_edges:
            remaining = len(top_items) - i - 1
            if remaining > 0:
                print(f"  {muted(f'... and {remaining} more nodes')}")
            break
    
    print(f"\n{muted('Legend: ■ Self │ ● Connected │ · No connection')}")
    print(f"{muted('Node color: ● Active │ ○ Inactive')}")
    print(f"{muted('Edge strength: ●●● Strong │ ●●○ Medium │ ●○○ Weak')}\n")


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
                    "access_count": access_count,
                    "activation": calculate_activation(item, current_time)
                })
            except Exception:
                pass
    
    all_accesses.sort(key=lambda x: x["last_access"], reverse=True)
    recent = all_accesses[:limit]
    
    print(f"\n{horizontal_rule()}")
    print(f"{header('  ACTIVATION TIMELINE')} {muted(f'(recent {len(recent)})')}")
    print(f"{horizontal_rule()}\n")
    
    if not recent:
        print(f"  {warning('No access history yet')}")
        return
    
    # Calculate bar width for sparklines
    max_count = max(item["access_count"] for item in recent) if recent else 1
    
    for idx, item in enumerate(recent):
        slug = item["slug"]
        relative = item["relative"]
        count = item["access_count"]
        activation = item["activation"]
        
        # Color based on recency
        if "just now" in relative or "m ago" in relative:
            marker_color = GREEN
            marker = "▶"
        elif "h ago" in relative:
            marker_color = CYAN
            marker = "▶"
        elif "d ago" in relative and int(relative.split("d")[0]) <= 2:
            marker_color = YELLOW
            marker = "▶"
        else:
            marker_color = GRAY
            marker = "○"
        
        # Activation bar
        act_bar = color_bar(activation, width=15)
        
        # Access count visualization
        count_bar_len = int((count / max_count) * 10)
        count_bar = f"{CYAN}{'█' * count_bar_len}{GRAY}{'░' * (10 - count_bar_len)}{RESET}"
        
        # Row number with leading zero for alignment
        row_num = f"{idx + 1:02d}"
        
        print(f"  {muted(row_num)} {marker_color}{marker}{RESET} {BOLD}{highlight(slug)}{RESET}")
        print(f"      {muted('Time:')} {relative:>12}  {muted('Count:')} {count_bar} ({count})")
        print(f"      {muted('Activation:')} {act_bar} {muted(f'{activation:.2f}')}")
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
        activations.append((slug, act, item))
    
    avg_activation = sum(a[1] for a in activations) / len(activations) if activations else 0
    high_activation = sum(1 for a in activations if a[1] > 0.5)
    medium_activation = sum(1 for a in activations if 0.25 < a[1] <= 0.5)
    low_activation = sum(1 for a in activations if a[1] <= 0.25)
    
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
        health_emoji = "✨"
    elif health_score >= 50:
        health_color = CYAN
        health_status = "HEALTHY"
        health_emoji = "💪"
    elif health_score >= 25:
        health_color = YELLOW
        health_status = "FAIR"
        health_emoji = "⚠️"
    else:
        health_color = RED
        health_status = "NEEDS ATTENTION"
        health_emoji = "🔴"
    
    print(f"\n{horizontal_rule(BOX_H, 60)}")
    print(f"{header('  MEMORY HEALTH DASHBOARD')}")
    print(f"{horizontal_rule(BOX_H, 60)}\n")
    
    # Health score box with gradient background effect
    score_bar_len = int(health_score / 5)
    score_bar = color_bar(health_score / 100, width=20, palette=ACTIVATION_PALETTE)
    
    print(f"  {BOX_TL}{BOX_H * 32}{BOX_TR}")
    print(f"  {BOX_V}  {health_emoji} {muted('OVERALL HEALTH:')} {health_color}{health_status:15}{RESET} {BOX_V}")
    print(f"  {BOX_V}     {muted('Score:')} {score_bar} {health_color}{health_score:>3}%{RESET}    {BOX_V}")
    print(f"  {BOX_BL}{BOX_H * 32}{BOX_BR}\n")
    
    # Stats section
    print(f"  {header('📊  MEMORY STATS')}")
    print(f"  {muted(BOX_H * 40)}")
    print(f"  {CYAN}├{RESET} {muted('Total Memories:')}    {highlight(str(total_items))}")
    print(f"  {CYAN}├{RESET} {muted('Total Tags:')}       {highlight(str(total_tags))}")
    print(f"  {CYAN}├{RESET} {muted('Tag Connections:')} {highlight(str(total_edges))}")
    print(f"  {CYAN}└{RESET} {muted('Total Accesses:')}  {highlight(str(total_accesses))}")
    print()
    
    # Activation distribution with nice bars
    print(f"  {header('📈  ACTIVATION DISTRIBUTION')}")
    print(f"  {muted(BOX_H * 40)}")
    
    bar_width = 25
    if total_items > 0:
        high_pct = high_activation / total_items
        med_pct = medium_activation / total_items
        low_pct = low_activation / total_items
        
        high_bar_len = int(high_pct * bar_width)
        med_bar_len = int(med_pct * bar_width)
        low_bar_len = int(low_pct * bar_width)
        
        # High activation (good - green)
        bar = f"{GREEN}{'█' * high_bar_len}{GRAY}{'░' * (bar_width - high_bar_len)}{RESET}"
        print(f"  {GREEN}█{RESET} {muted('High (>50%):')}  {bar} {highlight(f'{high_activation}')}")
        
        # Medium activation (warning - yellow)
        bar = f"{YELLOW}{'█' * med_bar_len}{GRAY}{'░' * (bar_width - med_bar_len)}{RESET}"
        print(f"  {YELLOW}█{RESET} {muted('Medium (25-50%):')} {bar} {highlight(f'{medium_activation}')}")
        
        # Low activation (bad - red)
        bar = f"{RED}{'█' * low_bar_len}{GRAY}{'░' * (bar_width - low_bar_len)}{RESET}"
        print(f"  {RED}█{RESET} {muted('Low (<25%):')}   {bar} {highlight(f'{low_activation}')}")
        
        # Percentage labels
        print(f"  {muted('            ')}  {GRAY}0%{' ' * (bar_width - 4)}100%{RESET}")
    else:
        print(f"  {muted('No data available')}")
    
    print()
    
    # Average metrics
    avg_pagerank = sum(pagerank.values()) / len(pagerank) if pagerank else 0
    
    print(f"  {header('📉  AVERAGE METRICS')}")
    print(f"  {muted(BOX_H * 40)}")
    print(f"  {CYAN}├{RESET} {muted('Avg Activation:')}   {highlight(f'{avg_activation:.2f}')}")
    print(f"  {CYAN}├{RESET} {muted('PageRank Avg:')}    {highlight(f'{avg_pagerank:.2f}')}")
    print(f"  {CYAN}└{RESET} {muted('Never Accessed:')}  ", end="")
    if items_never_accessed == 0:
        print(success(f'{items_never_accessed}'))
    elif items_never_accessed < total_items * 0.2:
        print(warning(f'{items_never_accessed}'))
    else:
        print(error(f'{items_never_accessed}'))
    
    # Top active memories section
    if activations:
        print()
        print(f"  {header('🔥  TOP ACTIVE MEMORIES')}")
        print(f"  {muted(BOX_H * 40)}")
        
        top_5 = sorted(activations, key=lambda x: x[1], reverse=True)[:5]
        for idx, (slug, act, _) in enumerate(top_5):
            act_bar = color_bar(act, width=12)
            rank_emoji = ["🥇", "🥈", "🥉", "4.", "5."][idx]
            print(f"  {rank_emoji} {highlight(slug[:25]):<25} {act_bar} {act:.2f}")
    
    print(f"\n{horizontal_rule(BOX_H, 60)}\n")


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
