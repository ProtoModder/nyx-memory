#!/usr/bin/env python3
"""
Nyx Memory REST API

Simple HTTP API for Nyx Memory with JSON responses.

Endpoints:
- GET /search?q=<query>     - Search memories
- GET /recent?limit=<n>     - Get recently accessed memories
- GET /tags                  - Get all tags

Usage:
    python3 api.py [--port PORT]

Default port: 8080
"""

import argparse
import json
import os
import sys
from http.server import HTTPServer, BaseHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlparse, parse_qs
from datetime import datetime, timezone

# Add memory directory to path
MEMORY_DIR = Path("/home/node/.openclaw/memory")
sys.path.insert(0, str(MEMORY_DIR))

# Import from existing memory modules
from db import (
    get_all_problems, get_problem, search_problems,
    get_stats, is_sqlite_available
)
from memory_utils import load_tag_graph, load_pagerank_scores


class NyxMemoryHandler(BaseHTTPRequestHandler):
    """HTTP request handler for Nyx Memory API."""

    def log_message(self, format, *args):
        """Log HTTP requests."""
        print(f"[{datetime.now().isoformat()}] {args[0]}")

    def send_json(self, data, status=200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(json.dumps(data, indent=2).encode())

    def do_GET(self):
        """Handle GET requests."""
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        # Route: /search
        if path == "/search":
            self.handle_search(query)
            return

        # Route: /recent
        if path == "/recent":
            self.handle_recent(query)
            return

        # Route: /tags
        if path == "/tags":
            self.handle_tags(query)
            return

        # Route: /health
        if path == "/health":
            self.send_json({"status": "ok", "timestamp": datetime.now().isoformat()})
            return

        # 404 for unknown routes
        self.send_json({"error": "Not found", "path": path}, status=404)

    def handle_search(self, query):
        """Handle /search endpoint."""
        q = query.get("q", [""])[0]
        limit = int(query.get("limit", [10])[0])

        if not q:
            self.send_json({"error": "Missing 'q' parameter"}, status=400)
            return

        try:
            # Use the existing search function
            results = search_problems(query=q, limit=limit)
            
            # Format results
            formatted = []
            for r in results:
                formatted.append({
                    "slug": r.get("slug"),
                    "title": r.get("title"),
                    "status": r.get("status"),
                    "priority": r.get("priority"),
                    "tags": r.get("tags", []),
                    "path": r.get("path"),
                    "access_count": r.get("access_count"),
                    "last_access": r.get("last_access")
                })

            self.send_json({
                "query": q,
                "count": len(formatted),
                "results": formatted
            })
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_recent(self, query):
        """Handle /recent endpoint."""
        limit = int(query.get("limit", [10])[0])
        limit = min(limit, 50)  # Cap at 50

        try:
            # Get all problems and sort by last access
            all_problems = get_all_problems()
            
            # Sort by last_access descending (most recent first)
            sorted_problems = sorted(
                all_problems,
                key=lambda p: p.get("last_access") or "",
                reverse=True
            )[:limit]

            formatted = []
            for p in sorted_problems:
                formatted.append({
                    "slug": p.get("slug"),
                    "title": p.get("title"),
                    "status": p.get("status"),
                    "priority": p.get("priority"),
                    "tags": p.get("tags", []),
                    "last_access": p.get("last_access")
                })

            self.send_json({
                "count": len(formatted),
                "results": formatted
            })
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)

    def handle_tags(self, query):
        """Handle /tags endpoint."""
        try:
            # Load tag graph to get all tags
            tag_graph = load_tag_graph()
            
            # Extract tags from graph
            tags_data = tag_graph.get("nodes", {})
            
            tags = []
            for tag, data in tags_data.items():
                tags.append({
                    "name": tag,
                    "count": data.get("count", 0),
                    "problems": data.get("problems", [])
                })

            # Sort by count descending
            tags.sort(key=lambda t: t["count"], reverse=True)

            self.send_json({
                "count": len(tags),
                "tags": tags
            })
        except Exception as e:
            self.send_json({"error": str(e)}, status=500)


def run_server(port=8080):
    """Run the API server."""
    # Check SQLite availability
    if not is_sqlite_available():
        print("Warning: SQLite database not available, using limited functionality")

    server_address = ("", port)
    httpd = HTTPServer(server_address, NyxMemoryHandler)
    print(f"Nyx Memory API running on http://localhost:{port}")
    print("Endpoints:")
    print(f"  GET /search?q=<query>     - Search memories")
    print(f"  GET /recent?limit=<n>    - Get recently accessed (default 10)")
    print(f"  GET /tags                 - Get all tags")
    print(f"  GET /health               - Health check")
    print(f"\nPress Ctrl+C to stop")

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down...")
        httpd.server_close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Nyx Memory REST API")
    parser.add_argument("--port", type=int, default=8080, help="Port to run on (default: 8080)")
    args = parser.parse_args()

    run_server(args.port)
