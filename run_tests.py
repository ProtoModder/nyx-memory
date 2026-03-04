#!/usr/bin/env python3
"""
Simple test runner for visualize.py tests.
Runs tests without pytest dependency.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

# Add the memory directory to the path
sys.path.insert(0, str(Path(__file__).parent / "memory"))

from visualize import (
    show_tag_cloud,
    show_relationship_graph,
    show_activation_timeline,
    show_dashboard,
    load_activation_log,
    load_tag_graph,
    load_pagerank_scores,
)


def create_temp_memory_dir(tmp_path):
    """Create a temporary memory directory with test data."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    
    # Create activation log
    activation_log = {
        "version": "1.0",
        "last_updated": "2026-03-04T20:00:00Z",
        "items": {
            "test-problem-1": {
                "path": "memory/problems/test-problem-1.md",
                "created": "2026-03-01T10:00:00Z",
                "access_times": ["2026-03-04T15:00:00Z", "2026-03-04T18:00:00Z"],
                "access_count": 2,
                "tags": ["python", "testing", "memory"]
            },
            "test-problem-2": {
                "path": "memory/problems/test-problem-2.md",
                "created": "2026-03-02T10:00:00Z",
                "access_times": ["2026-03-04T10:00:00Z"],
                "access_count": 1,
                "tags": ["automation", "testing"]
            },
            "test-problem-3": {
                "path": "memory/problems/test-problem-3.md",
                "created": "2026-03-03T10:00:00Z",
                "access_times": [],
                "access_count": 0,
                "tags": ["research"]
            }
        }
    }
    
    with open(memory_dir / "activation-log.json", "w") as f:
        json.dump(activation_log, f)
    
    # Create tag graph
    tag_graph = {
        "nodes": {
            "python": {"count": 5},
            "testing": {"count": 3},
            "memory": {"count": 2},
            "automation": {"count": 4},
            "research": {"count": 1}
        },
        "edges": [
            {"from": "python", "to": "testing", "weight": 2},
            {"from": "testing", "to": "automation", "weight": 1}
        ],
        "tag_index": {}
    }
    
    with open(memory_dir / "tag-graph.json", "w") as f:
        json.dump(tag_graph, f)
    
    # Create pagerank scores
    pagerank = {
        "scores": {
            "test-problem-1": 0.85,
            "test-problem-2": 0.65,
            "test-problem-3": 0.45
        }
    }
    
    with open(memory_dir / "pagerank-scores.json", "w") as f:
        json.dump(pagerank, f)
    
    return memory_dir


def run_tests():
    """Run all tests and report results."""
    import io
    from contextlib import redirect_stdout
    
    results = []
    tmp_path = Path(tempfile.mkdtemp())
    temp_memory_dir = create_temp_memory_dir(tmp_path)
    
    # Helper function to run a test
    def run_test(name, test_func):
        try:
            # Reset caches before each test
            import visualize
            visualize.activation_cache = None
            visualize.tag_graph_cache = None
            visualize.pagerank_cache = None
            
            with patch("visualize.MEMORY_BASE_DIR", temp_memory_dir):
                test_func()
            results.append((name, "PASS", None))
        except Exception as e:
            results.append((name, "FAIL", str(e)))
    
    # Test 1: show_tag_cloud with data
    def test_tag_cloud_data():
        f = io.StringIO()
        with redirect_stdout(f):
            show_tag_cloud(max_tags=5)
        output = f.getvalue()
        assert "TAG CLOUD" in output or "No tags found" in output
    
    # Test 2: show_relationship_graph with data
    def test_relationship_graph_data():
        f = io.StringIO()
        with redirect_stdout(f):
            show_relationship_graph(max_nodes=5, max_edges=10)
        output = f.getvalue()
        assert "RELATIONSHIP GRAPH" in output or "No items" in output
    
    # Test 3: show_activation_timeline with data
    def test_activation_timeline_data():
        f = io.StringIO()
        with redirect_stdout(f):
            show_activation_timeline(limit=5)
        output = f.getvalue()
        assert "ACTIVATION TIMELINE" in output or "No access history" in output
    
    # Test 4: show_dashboard with data
    def test_dashboard_data():
        f = io.StringIO()
        with redirect_stdout(f):
            show_dashboard()
        output = f.getvalue()
        assert "MEMORY HEALTH DASHBOARD" in output or "OVERALL HEALTH" in output
    
    # Test 5: load_activation_log
    def test_load_activation():
        import visualize
        visualize.activation_cache = None
        with patch("visualize.ACTIVATION_LOG", temp_memory_dir / "activation-log.json"):
            data = load_activation_log(force_reload=True)
        assert "items" in data
        assert len(data["items"]) == 3
    
    # Test 6: load_tag_graph
    def test_load_tag_graph():
        import visualize
        visualize.tag_graph_cache = None
        with patch("visualize.TAG_GRAPH_PATH", temp_memory_dir / "tag-graph.json"):
            data = load_tag_graph(force_reload=True)
        assert "nodes" in data
        assert len(data["nodes"]) == 5
    
    # Test 7: load_pagerank_scores
    def test_load_pagerank():
        import visualize
        visualize.pagerank_cache = None
        with patch("visualize.PAGERANK_SCORES_PATH", temp_memory_dir / "pagerank-scores.json"):
            data = load_pagerank_scores(force_reload=True)
        assert len(data) == 3
        assert data["test-problem-1"] == 0.85
    
    # Run all tests
    run_test("test_show_tag_cloud_with_data", test_tag_cloud_data)
    run_test("test_show_relationship_graph_with_data", test_relationship_graph_data)
    run_test("test_show_activation_timeline_with_data", test_activation_timeline_data)
    run_test("test_show_dashboard_with_data", test_dashboard_data)
    run_test("test_load_activation_log", test_load_activation)
    run_test("test_load_tag_graph", test_load_tag_graph)
    run_test("test_load_pagerank_scores", test_load_pagerank)
    
    # Print results
    print("=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    
    passed = 0
    failed = 0
    
    for name, status, error in results:
        if status == "PASS":
            print(f"✓ {name}")
            passed += 1
        else:
            print(f"✗ {name}")
            print(f"  Error: {error}")
            failed += 1
    
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)
    
    return failed == 0


if __name__ == "__main__":
    success = run_tests()
    sys.exit(0 if success else 1)
