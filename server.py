#!/usr/bin/env python3
"""
Command Center Backend Server
Serves the dashboard and provides JSON endpoints for system data
"""

import json
import os
from http.server import HTTPServer, SimpleHTTPRequestHandler
from datetime import datetime
from functools import partial
import subprocess

PORT = 8766
DIRECTORY = os.path.expanduser("~/.openclaw/workspace")

class CORSRequestHandler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=DIRECTORY, **kwargs)
    
    def end_headers(self):
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, OPTIONS')
        self.send_header('Cache-Control', 'no-store')
        super().end_headers()
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.end_headers()
    
    def do_GET(self):
        if self.path == '/api/status':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_system_status()).encode())
        elif self.path == '/api/memory':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_memory_stats()).encode())
        elif self.path == '/api/activity':
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            self.wfile.write(json.dumps(get_recent_activity()).encode())
        else:
            super().do_GET()

def get_system_status():
    """Get current system metrics"""
    # Get memory info from /proc/meminfo
    mem_info = {}
    try:
        with open('/proc/meminfo', 'r') as f:
            for line in f:
                parts = line.split()
                if len(parts) >= 2:
                    mem_info[parts[0].rstrip(':')] = int(parts[1]) * 1024  # Convert to bytes
    except:
        mem_info = {'MemTotal': 0, 'MemAvailable': 0, 'MemFree': 0}
    
    total = mem_info.get('MemTotal', 0)
    available = mem_info.get('MemAvailable', 0)
    used = total - available
    
    # Get CPU usage
    try:
        result = subprocess.run(['cat', '/proc/loadavg'], capture_output=True, text=True)
        load_parts = result.stdout.strip().split()
        load_avg = [float(load_parts[i]) for i in range(3)] if len(load_parts) >= 3 else [0, 0, 0]
    except:
        load_avg = [0, 0, 0]
    
    # Get CPU count
    try:
        result = subprocess.run(['nproc'], capture_output=True, text=True)
        cpu_count = int(result.stdout.strip())
    except:
        cpu_count = 1
    
    # Calculate percentage
    mem_percent = (used / total * 100) if total > 0 else 0
    
    return {
        "ram": {
            "total": total,
            "used": used,
            "percent": mem_percent,
            "available": available
        },
        "cpu": {
            "percent": min(load_avg[0] * 100 / cpu_count, 100),
            "count": cpu_count
        },
        "load": {
            "1min": load_avg[0],
            "5min": load_avg[1],
            "15min": load_avg[2]
        },
        "timestamp": datetime.now().isoformat()
    }

def get_memory_stats():
    """Get memory/knowledge base stats"""
    base_path = os.path.expanduser("~/.openclaw/memory")
    
    stats = {
        "problems": {"count": 0, "open": 0, "resolved": 0},
        "tags": {"count": 0},
        "recall": {"last_access": None}
    }
    
    # Count problems
    problems_dir = os.path.join(base_path, "problems")
    if os.path.exists(problems_dir):
        for f in os.listdir(problems_dir):
            if f.endswith('.md'):
                stats["problems"]["count"] += 1
                try:
                    with open(os.path.join(problems_dir, f), 'r') as fp:
                        content = fp.read().lower()
                        if '**status:** resolved' in content:
                            stats["problems"]["resolved"] += 1
                        elif '**status:** open' in content:
                            stats["problems"]["open"] += 1
                except:
                    pass
    
    # Count tags
    tag_graph = os.path.join(base_path, "tag-graph.json")
    if os.path.exists(tag_graph):
        try:
            with open(tag_graph, 'r') as f:
                data = json.load(f)
                stats["tags"]["count"] = len(data.get('nodes', {}))
        except:
            pass
    
    # Last activation access
    activation_log = os.path.join(base_path, "activation-log.json")
    if os.path.exists(activation_log):
        try:
            with open(activation_log, 'r') as f:
                data = json.load(f)
                if data.get('access_times'):
                    latest = max(data['access_times'].values())
                    stats["recall"]["last_access"] = latest
        except:
            pass
    
    stats["timestamp"] = datetime.now().isoformat()
    return stats

def get_recent_activity():
    """Get recent activity log entries"""
    base_path = os.path.expanduser("~/.openclaw/memory")
    today = datetime.now().strftime("%Y-%m-%d")
    activity_file = os.path.join(base_path, f"{today}.md")
    
    activities = []
    
    if os.path.exists(activity_file):
        try:
            with open(activity_file, 'r') as f:
                lines = f.readlines()
                # Get last 10 non-empty lines
                for line in reversed(lines[-20:]):
                    line = line.strip()
                    if line and not line.startswith('#'):
                        activities.append(line)
                        if len(activities) >= 10:
                            break
        except:
            pass
    
    # Add some default activities if none exist
    if not activities:
        activities = [
            "System initialized",
            "Memory systems online",
            "Command center activated"
        ]
    
    return {
        "activities": list(reversed(activities)),
        "timestamp": datetime.now().isoformat()
    }

def run_server():
    """Start the HTTP server"""
    handler = partial(CORSRequestHandler)
    server = HTTPServer(('0.0.0.0', PORT), handler)
    
    print(f"🚀 Command Center server running at http://localhost:{PORT}")
    print(f"📊 Dashboard: http://localhost:{PORT}/command-center.html")
    print(f"📡 API Endpoints:")
    print(f"   - http://localhost:{PORT}/api/status")
    print(f"   - http://localhost:{PORT}/api/memory")
    print(f"   - http://localhost:{PORT}/api/activity")
    print(f"\nPress Ctrl+C to stop")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Server stopped")
        server.shutdown()

if __name__ == "__main__":
    run_server()
