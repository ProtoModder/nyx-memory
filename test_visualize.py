#!/usr/bin/env python3
"""
Tests for visualize.py

Tests the visualization functions to ensure they run without errors.
"""

import json
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest


# Add the memory directory to the path
sys.path.insert(0, str(Path(__file__).parent.parent / "memory"))

from visualize import (
    show_tag_cloud,
    show_relationship_graph,
    show_activation_timeline,
    show_dashboard,
    load_activation_log,
    load_tag_graph,
    load_pagerank_scores,
)


# ============================================================================
# FIXTURES
# ============================================================================

@pytest.fixture
def temp_memory_dir(tmp_path):
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


@pytest.fixture
def empty_memory_dir(tmp_path):
    """Create a temporary memory directory with no data."""
    memory_dir = tmp_path / "memory"
    memory_dir.mkdir()
    return memory_dir


# ============================================================================
# TESTS
# ============================================================================

def test_show_tag_cloud_with_data(temp_memory_dir, capsys):
    """Test show_tag_cloud runs without error with existing data."""
    with patch("visualize.ACTIVATION_LOG", temp_memory_dir / "activation-log.json"):
        with patch("visualize.TAG_GRAPH_PATH", temp_memory_dir / "tag-graph.json"):
            # Force reload to pick up temp data
            import visualize
            visualize.activation_cache = None
            visualize.tag_graph_cache = None
            
            # Should not raise any exceptions
            show_tag_cloud(max_tags=5)
            
            captured = capsys.readouterr()
            # Verify output contains expected elements
            assert "TAG CLOUD" in captured.out or "No tags found" in captured.out


def test_show_tag_cloud_empty(empty_memory_dir, capsys):
    """Test show_tag_cloud handles empty data gracefully."""
    with patch("visualize.MEMORY_BASE_DIR", empty_memory_dir):
        import visualize
        visualize.activation_cache = None
        visualize.tag_graph_cache = None
        
        # Should not raise any exceptions
        show_tag_cloud()
        
        captured = capsys.readouterr()
        assert "No tags found" in captured.out or "TAG CLOUD" in captured.out


def test_show_relationship_graph_with_data(temp_memory_dir, capsys):
    """Test show_relationship_graph runs without error with existing data."""
    with patch("visualize.MEMORY_BASE_DIR", temp_memory_dir):
        import visualize
        visualize.activation_cache = None
        visualize.tag_graph_cache = None
        
        # Should not raise any exceptions
        show_relationship_graph(max_nodes=5, max_edges=10)
        
        captured = capsys.readouterr()
        assert "RELATIONSHIP GRAPH" in captured.out or "No items" in captured.out


def test_show_relationship_graph_empty(empty_memory_dir, capsys):
    """Test show_relationship_graph handles empty data gracefully."""
    with patch("visualize.MEMORY_BASE_DIR", empty_memory_dir):
        import visualize
        visualize.activation_cache = None
        visualize.tag_graph_cache = None
        
        # Should not raise any exceptions
        show_relationship_graph()
        
        captured = capsys.readouterr()
        assert "No items" in captured.out or "RELATIONSHIP GRAPH" in captured.out


def test_show_activation_timeline_with_data(temp_memory_dir, capsys):
    """Test show_activation_timeline runs without error with existing data."""
    with patch("visualize.MEMORY_BASE_DIR", temp_memory_dir):
        import visualize
        visualize.activation_cache = None
        visualize.tag_graph_cache = None
        
        # Should not raise any exceptions
        show_activation_timeline(limit=5)
        
        captured = capsys.readouterr()
        assert "ACTIVATION TIMELINE" in captured.out or "No access history" in captured.out


def test_show_activation_timeline_empty(empty_memory_dir, capsys):
    """Test show_activation_timeline handles empty data gracefully."""
    with patch("visualize.MEMORY_BASE_DIR", empty_memory_dir):
        import visualize
        visualize.activation_cache = None
        visualize.tag_graph_cache = None
        
        # Should not raise any exceptions
        show_activation_timeline()
        
        captured = capsys.readouterr()
        assert "No items" in captured.out or "ACTIVATION TIMELINE" in captured.out


def test_show_dashboard_with_data(temp_memory_dir, capsys):
    """Test show_dashboard runs without error with existing data."""
    with patch("visualize.MEMORY_BASE_DIR", temp_memory_dir):
        import visualize
        visualize.activation_cache = None
        visualize.tag_graph_cache = None
        visualize.pagerank_cache = None
        
        # Should not raise any exceptions
        show_dashboard()
        
        captured = capsys.readouterr()
        assert "MEMORY HEALTH DASHBOARD" in captured.out or "OVERALL HEALTH" in captured.out


def test_show_dashboard_empty(empty_memory_dir, capsys):
    """Test show_dashboard handles empty data gracefully."""
    with patch("visualize.MEMORY_BASE_DIR", empty_memory_dir):
        import visualize
        visualize.activation_cache = None
        visualize.tag_graph_cache = None
        visualize.pagerank_cache = None
        
        # Should not raise any exceptions
        show_dashboard()
        
        captured = capsys.readouterr()
        assert "MEMORY HEALTH DASHBOARD" in captured.out or "OVERALL HEALTH" in captured.out


def test_load_activation_log(temp_memory_dir):
    """Test loading activation log works correctly."""
    with patch("visualize.ACTIVATION_LOG", temp_memory_dir / "activation-log.json"):
        import visualize
        visualize.activation_cache = None
        
        data = load_activation_log(force_reload=True)
        
        assert "items" in data
        assert len(data["items"]) == 3


def test_load_tag_graph(temp_memory_dir):
    """Test loading tag graph works correctly."""
    with patch("visualize.TAG_GRAPH_PATH", temp_memory_dir / "tag-graph.json"):
        import visualize
        visualize.tag_graph_cache = None
        
        data = load_tag_graph(force_reload=True)
        
        assert "nodes" in data
        assert len(data["nodes"]) == 5


def test_load_pagerank_scores(temp_memory_dir):
    """Test loading pagerank scores works correctly."""
    with patch("visualize.PAGERANK_SCORES_PATH", temp_memory_dir / "pagerank-scores.json"):
        import visualize
        visualize.pagerank_cache = None
        
        data = load_pagerank_scores(force_reload=True)
        
        assert len(data) == 3
        assert data["test-problem-1"] == 0.85


# ============================================================================
# RUN TESTS
# ============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
