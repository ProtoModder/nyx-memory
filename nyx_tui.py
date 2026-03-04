#!/usr/bin/env python3
"""
Nyx Memory System TUI - Interactive Text User Interface

A menu-driven interface for interacting with Nyx's memory system.
Features:
- Search with live results
- List recent problems
- View problem details
- Record access (interact with memory)
- Show tags
- Clear cache
"""

import subprocess
from datetime import datetime, timezone
from pathlib import Path

# Import shared utilities
import memory_utils
from memory_utils import (
    load_activation_log,
    save_activation_log,
    load_tags_from_file,
    get_status_from_file,
    calculate_activation,
    BASE_LEVEL,
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

# Configuration
MEMORY_DIR = Path("/home/node/.openclaw/workspace")


def clear_screen():
    """Clear the terminal screen."""
    import os
    os.system('clear' if os.name == 'posix' else 'cls')


def pause():
    """Wait for user input."""
    input(muted("\nPress Enter to continue..."))


def record_access(slug):
    """Record access to a problem."""
    data = load_activation_log()
    current_time = datetime.now(timezone.utc)
    
    if slug in data["items"]:
        item = data["items"][slug]
        item["access_times"].append(current_time.isoformat())
        item["access_count"] = item.get("access_count", 0) + 1
    else:
        data["items"][slug] = {
            "slug": slug,
            "path": f"memory/problems/{slug}.md",
            "created": current_time.isoformat(),
            "access_times": [current_time.isoformat()],
            "access_count": 1,
            "tags": []
        }
    
    item = data["items"][slug]
    item["activation"] = calculate_activation(item, current_time)
    save_activation_log(data)
    return item["activation"]


def search_memory(query, max_results=10):
    """Search memory using qmd."""
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
    except Exception as e:
        print(f"{error('Search error:')} {e}")
        return []


def get_problem_content(slug):
    """Get the content of a problem file."""
    paths = [
        MEMORY_DIR / "memory/problems" / f"{slug}.md",
        MEMORY_DIR / f"{slug}.md",
    ]
    
    for path in paths:
        if path.exists():
            return path.read_text()
    return None


def get_tags_from_file(slug):
    """Extract tags from a problem file (wrapper for memory_utils)."""
    path = f"memory/problems/{slug}.md"
    return memory_utils.load_tags_from_file(path)


def get_status_from_file(slug):
    """Extract status from a problem file (wrapper for memory_utils)."""
    path = f"memory/problems/{slug}.md"
    return memory_utils.get_status_from_file(path)


def clear_cache():
    """Clear the query cache."""
    try:
        result = subprocess.run(
            ["python3", str(MEMORY_BASE_DIR / "memory/actr_ranker.py"), "--clear-cache"],
            capture_output=True,
            text=True,
            timeout=10
        )
        return True
    except Exception:
        return False


# Menu Functions

def menu_search():
    """Search menu."""
    clear_screen()
    print(header("\n=== 🔍 Search Memory ===\n"))
    
    query = input("Enter search query: ").strip()
    if not query:
        print(warning("Empty query. Returning to menu."))
        pause()
        return
    
    results = search_memory(query)
    
    if not results:
        print(f"\n{warning('No results found for')} '{query}'")
        pause()
        return
    
    print(f"\n{header(f'Results for:')} '{query}'\n")
    
    data = load_activation_log()
    current_time = datetime.now(timezone.utc)
    
    for i, r in enumerate(results, 1):
        slug = r['slug']
        score = r['qmd_score']
        
        if slug in data["items"]:
            activation = data["items"][slug].get("activation", 0.0)
            access_count = data["items"][slug].get("access_count", 0)
        else:
            activation = 0.0
            access_count = 0
        
        tags = get_tags_from_file(slug)
        status = get_status_from_file(slug)
        
        # Color code the score
        score_color = GREEN if score > 0.5 else YELLOW if score > 0.25 else RED
        status_color = GREEN if status == "resolved" else YELLOW if status == "in-progress" else GRAY
        
        print(f"{highlight(f'{i}. {slug}')}")
        print(f"   {muted('Score:')} {colorize(f'{score:.2f}', score_color)} | {muted('Status:')} {colorize(status, status_color)}")
        print(f"   {muted('Activation:')} {activation:.3f} | {muted('Accesses:')} {access_count}")
        if tags:
            print(f"   {muted('Tags:')} {', '.join(tags)}")
        print()
    
    print(f"{muted('Select a number to view details, or press Enter to return...')}")
    choice = input(muted("\n> ")).strip()
    
    if choice.isdigit() and 1 <= int(choice) <= len(results):
        slug = results[int(choice) - 1]["slug"]
        view_problem(slug)
    else:
        return


def menu_list_recent():
    """List recent problems menu."""
    clear_screen()
    print(header("\n=== 📋 Recent Problems ===\n"))
    
    data = load_activation_log()
    current_time = datetime.now(timezone.utc)
    
    if not data["items"]:
        print(warning("No problems tracked yet."))
        pause()
        return
    
    items = []
    for slug, item in data["items"].items():
        activation = calculate_activation(item, current_time)
        access_count = item.get("access_count", 0)
        created = item.get("created", "")
        
        # Get last access time
        access_times = item.get("access_times", [])
        last_access = access_times[-1] if access_times else created
        
        items.append({
            "slug": slug,
            "activation": activation,
            "access_count": access_count,
            "created": created,
            "last_access": last_access,
            "status": get_status_from_file(slug),
            "tags": get_tags_from_file(slug)
        })
    
    # Sort by last access (most recent first)
    items.sort(key=lambda x: x["last_access"], reverse=True)
    
    print(f"{muted(f'Total: {len(items)} problems')}\n")
    
    for i, item in enumerate(items, 1):
        slug = item["slug"]
        status = item["status"]
        tags = item["tags"]
        
        status_color = GREEN if status == "resolved" else YELLOW if status == "in-progress" else GRAY
        
        print(f"{highlight(f'{i}. {slug}')}")
        print(f"   {muted('Status:')} {colorize(status, status_color)}")
        print(f"   {muted('Activation:')} {item['activation']:.3f} | {muted('Accesses:')} {item['access_count']}")
        if tags:
            print(f"   {muted('Tags:')} {', '.join(tags)}")
        print()
    
    print(f"{muted('Select a number to view details, or press Enter to return...')}")
    choice = input(muted("\n> ")).strip()
    
    if choice.isdigit() and 1 <= int(choice) <= len(items):
        slug = items[int(choice) - 1]["slug"]
        view_problem(slug)
    else:
        return


def view_problem(slug):
    """View problem details."""
    clear_screen()
    print(header(f"\n=== 📄 Problem: {slug} ===\n"))
    
    content = get_problem_content(slug)
    
    if content:
        # Record access
        activation = record_access(slug)
        print(success(f"✓ Access recorded (Activation: {activation:.3f})\n"))
        
        # Show first 50 lines of content
        lines = content.split('\n')[:50]
        print(muted("--- Content Preview ---"))
        for line in lines:
            print(line)
        
        if len(content.split('\n')) > 50:
            print(muted(f"\n... ({len(content.split('\n')) - 50} more lines)"))
    else:
        print(warning(f"No content found for {slug}"))
    
    # Show metadata
    data = load_activation_log()
    if slug in data["items"]:
        item = data["items"][slug]
        print(f"\n{header('--- Metadata ---')}")
        print(f"{muted('Created:')} {item.get('created', 'unknown')}")
        print(f"{muted('Access Count:')} {item.get('access_count', 0)}")
        print(f"{muted('Activation:')} {item.get('activation', 0):.3f}")
        
        tags = get_tags_from_file(slug)
        if tags:
            print(f"{muted('Tags:')} {', '.join(tags)}")
        
        status = get_status_from_file(slug)
        print(f"{muted('Status:')} {status}")
    
    pause()


def menu_record_access():
    """Record access menu."""
    clear_screen()
    print(header("\n=== 📝 Record Access ===\n"))
    
    # Show recent items for reference
    data = load_activation_log()
    if data["items"]:
        print(muted("Recent items:"))
        items = sorted(
            data["items"].items(),
            key=lambda x: x[1].get("access_times", [""])[-1],
            reverse=True
        )[:5]
        for slug, item in items:
            print(f"  - {slug}")
        print()
    
    slug = input("Enter problem slug to record access: ").strip()
    
    if not slug:
        print(warning("Empty slug. Returning to menu."))
        pause()
        return
    
    activation = record_access(slug)
    print(success(f"\n✓ Access recorded for {slug}"))
    print(f"{muted('New activation:')} {activation:.3f}")
    pause()


def menu_show_tags():
    """Show tags menu."""
    clear_screen()
    print(header("\n=== 🏷️ All Tags ===\n"))
    
    data = load_activation_log()
    all_tags = {}
    
    for slug, item in data["items"].items():
        tags = get_tags_from_file(slug)
        for tag in tags:
            if tag not in all_tags:
                all_tags[tag] = []
            all_tags[tag].append(slug)
    
    if not all_tags:
        print(warning("No tags found."))
        pause()
        return
    
    # Sort tags by frequency
    sorted_tags = sorted(all_tags.items(), key=lambda x: len(x[1]), reverse=True)
    
    for tag, slugs in sorted_tags:
        print(f"{highlight(tag)} ({len(slugs)} problems)")
        print(f"   {muted(', '.join(slugs))}")
        print()
    
    pause()


def menu_clear_cache():
    """Clear cache menu."""
    clear_screen()
    print(header("\n=== 🗑️ Clear Cache ===\n"))
    
    confirm = input("Are you sure you want to clear the query cache? (y/N): ").strip().lower()
    
    if confirm == 'y':
        if clear_cache():
            print(success("\n✓ Cache cleared successfully"))
        else:
            print(error("\n✗ Failed to clear cache"))
    else:
        print(warning("\nCancelled"))
    
    pause()


def menu_exit():
    """Exit menu."""
    clear_screen()
    print(header("\n=== 👋 Goodbye! ===\n"))
    print(f"{muted('Nyx Memory TUI v1.0')}")
    print()


def main_menu():
    """Main menu loop."""
    while True:
        clear_screen()
        print(header("╔══════════════════════════════════════╗"))
        print(header("║     🧠 Nyx Memory System TUI         ║"))
        print(header("╚══════════════════════════════════════╝"))
        print()
        print(f"  {highlight('1.')} Search memory")
        print(f"  {highlight('2.')} List recent problems")
        print(f"  {highlight('3.')} Record access")
        print(f"  {highlight('4.')} Show all tags")
        print(f"  {highlight('5.')} Clear cache")
        print(f"  {highlight('0.')} Exit")
        print()
        
        choice = input(muted("Select an option: ")).strip()
        
        if choice == '1':
            menu_search()
        elif choice == '2':
            menu_list_recent()
        elif choice == '3':
            menu_record_access()
        elif choice == '4':
            menu_show_tags()
        elif choice == '5':
            menu_clear_cache()
        elif choice == '0':
            menu_exit()
            break
        else:
            print(warning("Invalid option. Please try again."))
            pause()


if __name__ == "__main__":
    main_menu()
