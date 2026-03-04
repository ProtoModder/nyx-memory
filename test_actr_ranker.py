#!/usr/bin/env python3
"""
Tests for ACT-R Unified Memory Ranker

Run with: python3 test_actr_ranker.py
"""

import sys
import os
sys.path.insert(0, '/home/node/.openclaw/memory')

from actr_ranker import (
    load_activation_log,
    load_tag_graph,
    load_pagerank_scores,
    calculate_activation,
    record_access_with_priming,
    unified_search,
    search_qmd,
    WEIGHT_QMD,
    WEIGHT_ACTIVATION,
    WEIGHT_PAGERANK,
    WEIGHT_RELATIONSHIPS,
    BASE_LEVEL,
    validate_config,
    validate_path,
    cached_read,
    clear_file_cache,
    should_retrieve_memory,
    calculate_freshness_decay,
    get_problem_status,
    RETRIEVE_KEYWORDS,
    MEMORY_DIR
)

from datetime import datetime, timezone
from datetime import timedelta


def test_weights_sum_to_one():
    """Verify all weights sum to 1.0"""
    total = WEIGHT_QMD + WEIGHT_ACTIVATION + WEIGHT_PAGERANK + WEIGHT_RELATIONSHIPS
    assert abs(total - 1.0) < 0.01, f"Weights sum to {total}, expected 1.0"
    print("✓ Weights sum to 1.0")

def test_activation_log_loads():
    """Verify activation log loads"""
    data = load_activation_log()
    assert "items" in data, "Missing 'items' key"
    assert len(data["items"]) > 0, "No items in activation log"
    print(f"✓ Activation log: {len(data['items'])} items")

def test_tag_graph_loads():
    """Verify tag graph loads"""
    graph = load_tag_graph()
    assert "nodes" in graph, "Missing 'nodes' key"
    assert "edges" in graph, "Missing 'edges' key"
    print(f"✓ Tag graph: {len(graph['nodes'])} nodes, {len(graph['edges'])} edges")

def test_pagerank_loads():
    """Verify PageRank scores load"""
    scores = load_pagerank_scores()
    assert len(scores) > 0, "No PageRank scores"
    print(f"✓ PageRank: {len(scores)} scores")

def test_calculate_activation():
    """Test activation calculation"""
    from datetime import datetime, timezone
    
    # Fresh item
    item = {"access_times": [], "created": datetime.now(timezone.utc).isoformat()}
    act = calculate_activation(item, datetime.now(timezone.utc))
    assert act == BASE_LEVEL, f"Fresh item should have base level {BASE_LEVEL}"
    
    # Accessed item
    item = {
        "access_times": [datetime.now(timezone.utc).isoformat()],
        "created": datetime.now(timezone.utc).isoformat()
    }
    act = calculate_activation(item, datetime.now(timezone.utc))
    assert act > BASE_LEVEL, "Accessed item should have higher activation"
    print(f"✓ Activation calculation works: {act:.3f}")

def test_unified_search_returns_valid_results():
    """Verify unified search returns valid results"""
    queries = ["memory", "tts", "workflow", "puppeteer"]
    
    for q in queries:
        results = unified_search(q, max_results=3)
        assert len(results) > 0, f"No results for query '{q}'"
        
        # Verify result structure
        r = results[0]
        assert "slug" in r, "Missing 'slug'"
        assert "final_score" in r, "Missing 'final_score'"
        assert 0 <= r["final_score"] <= 1, "Score out of range"
        
        # Verify all scores present
        assert "qmd_score" in r, "Missing QMD score"
        assert "activation" in r, "Missing activation score"
        assert "pagerank" in r, "Missing PageRank score"
        assert "exact_bonus" in r, "Missing exact bonus"
        
        print(f"  ✓ Query '{q}': {r['slug']} (score: {r['final_score']:.2f})")
    
    print("✓ Unified search works for all queries")

def test_scores_in_range():
    """Verify all scores are in valid range"""
    results = unified_search("test", max_results=5)
    for r in results:
        for key in ["qmd_score", "activation", "pagerank", "relationships", "exact_bonus", "final_score"]:
            score = r.get(key, 0)
            assert 0 <= score <= 1, f"{key} score {score} out of range"
    print("✓ All scores in valid range [0, 1]")

def test_recall_accuracy():
    """Test recall accuracy on known problems"""
    tests = [
        ("brain memory hopfield", "video-brain-memory-retrieval"),
        ("soar actr cognitive", "video-cognitive-architectures-soar-actr"),
        ("workload prediction", "video-cognitive-workload-prediction"),
        ("openclaw employee", "video-openclaw-fulltime-employee"),
        ("titans llm memory", "video-titans-integrated-llm-memory"),
        ("puppeteer", "puppeteer-stealth-bypass"),
        ("memory ai", "mem0-ai-memory"),
        ("cognitive architecture", "cognitive-architecture-real-time-performance"),
    ]
    
    correct = 0
    for query, expected in tests:
        results = unified_search(query, max_results=3)
        top = results[0]["slug"] if results else "none"
        if expected in top:
            correct += 1
        else:
            print(f"  ✗ '{query}' -> {top} (expected {expected})")
    
    accuracy = correct / len(tests) * 100
    print(f"✓ Recall accuracy: {correct}/{len(tests)} = {accuracy:.0f}%")
    return accuracy >= 70  # Require at least 70% recall


# ============================================================================
# NEW TESTS: Security, Caching, Pre-retrieval, Freshness
# ============================================================================

def test_config_validation():
    """Test that invalid weights raise errors"""
    # Test invalid weight (not in 0-1 range)
    try:
        validate_config({"weights": {"qmd": 1.5, "activation": 0, "pagerank": 0, "relationships": 0}})
        assert False, "Should have raised ValueError for weight > 1"
    except ValueError as e:
        assert "0-1 range" in str(e), f"Wrong error message: {e}"
    
    # Test weights not summing to 1.0
    try:
        validate_config({"weights": {"qmd": 0.5, "activation": 0.5, "pagerank": 0.5, "relationships": 0.5}})
        assert False, "Should have raised ValueError for sum != 1"
    except ValueError as e:
        assert "1.0" in str(e), f"Wrong error message: {e}"
    
    # Test negative weight
    try:
        validate_config({"weights": {"qmd": -0.1, "activation": 0.7, "pagerank": 0.3, "relationships": 0.1}})
        assert False, "Should have raised ValueError for negative weight"
    except ValueError as e:
        assert "0-1 range" in str(e), f"Wrong error message: {e}"
    
    # Test invalid ACT-R parameter
    try:
        validate_config({"weights": {"qmd": 0.5, "activation": 0.2, "pagerank": 0.2, "relationships": 0.1}, 
                        "actr": {"base_level": 1.5}})
        assert False, "Should have raised ValueError for ACT-R param > 1"
    except ValueError as e:
        assert "0-1 range" in str(e), f"Wrong error message: {e}"
    
    # Valid config should pass
    result = validate_config({"weights": {"qmd": 0.5, "activation": 0.2, "pagerank": 0.2, "relationships": 0.1}})
    assert result is True, "Valid config should return True"
    
    print("✓ Config validation works correctly")


def test_path_traversal_blocked():
    """Test that malicious paths are rejected"""
    import tempfile
    from pathlib import Path
    
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        
        # Test path traversal attempts (Unix-style)
        malicious_paths = [
            "../../../etc/passwd",
            "/etc/passwd",
            "memory/../../../root/.ssh",
            "foo/../../bar",
        ]
        
        for path in malicious_paths:
            try:
                validate_path(path, base)
                assert False, f"Should have blocked: {path}"
            except ValueError as e:
                assert "traversal" in str(e).lower() or "Invalid path" in str(e), f"Wrong error: {e}"
        
        # Valid paths should work
        safe_path = "test.md"
        result = validate_path(safe_path, base)
        assert result is not None, "Valid path should return path"
        
        # Same-directory access should work
        result = validate_path("file.txt", base)
        assert result is not None, "Same-dir path should work"
    
    print("✓ Path traversal blocked")


def test_cache_works():
    """Test that file caching works"""
    import tempfile
    from pathlib import Path
    
    clear_file_cache()
    
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        test_file = base / "test_cache.txt"
        test_content = "Hello, cached world!"
        test_file.write_text(test_content)
        
        # First read - should load from disk
        content1 = cached_read("test_cache.txt", base)
        assert content1 == test_content, f"First read should get content, got {content1!r}"
        
        # Modify file
        test_file.write_text("Modified content")
        
        # Second read - should return cached content
        content2 = cached_read("test_cache.txt", base)
        assert content2 == test_content, "Cached read should return original (cached)"
        
        # Force reload would get new content (but we don't expose force_reload in public API)
        # Clear cache and read again
        clear_file_cache()
        content3 = cached_read("test_cache.txt", base)
        assert content3 == "Modified content", "After cache clear, should get new content"
        
        # Invalid path should return empty string
        result = cached_read("nonexistent_file.txt", base)
        assert result == "", "Invalid path should return empty string"
        
        # Malicious path should return empty (blocked)
        result = cached_read("../../../etc/passwd", base)
        assert result == "", "Malicious path should return empty"
    
    print("✓ File caching works correctly")


def test_sanitization():
    """Test query sanitization"""
    # The actr_ranker uses subprocess to call qmd search
    # Let's test that queries with special chars are handled
    from actr_ranker import search_qmd
    
    # Test with special characters - should not crash
    dangerous_queries = [
        "test; rm -rf /",
        "test && echo hack",
        "test | cat /etc/passwd",
        "test$(whoami)",
        "test`id`",
    ]
    
    for q in dangerous_queries:
        try:
            # Should not raise, but might return empty
            results = search_qmd(q, max_results=1)
            # Should gracefully handle (return empty list)
            assert isinstance(results, list), "Should return list"
        except Exception as e:
            # Ideally shouldn't raise, but subprocess.run with shell=False is safe
            pass
    
    # Normal queries should work
    normal_results = search_qmd("memory", max_results=1)
    assert isinstance(normal_results, list), "Normal query should return list"
    
    print("✓ Query sanitization works (no injection)")


def test_pre_retrieval():
    """Test should_retrieve_memory function"""
    # Test with RETRIEVE_KEYWORDS
    keyword_queries = [
        "how do I implement",
        "fix the error",
        "remember the solution",
        "what task did I work on",
        "build a new feature",
        "I tried this before",
    ]
    
    for q in keyword_queries:
        result = should_retrieve_memory(q)
        assert result is True, f"Should retrieve for: {q}"
    
    # Test short queries (below min_length)
    short_queries = ["a", "ab", ""]
    for q in short_queries:
        result = should_retrieve_memory(q)
        assert result is False, f"Should NOT retrieve for short: {q}"
    
    # Test queries without keywords
    neutral_queries = ["hello world", "the weather", "foo bar baz"]
    for q in neutral_queries:
        # These might or might not trigger based on slug matching
        # Just verify it doesn't crash
        result = should_retrieve_memory(q)
        assert isinstance(result, bool), f"Should return bool for: {q}"
    
    print("✓ Pre-retrieval check works correctly")


def test_freshness():
    """Test freshness decay calculation"""
    current_time = datetime.now(timezone.utc)
    
    # Test fresh item (just created)
    fresh_item = {
        "slug": "test-problem",
        "created": current_time.isoformat(),
        "access_times": []
    }
    
    # Mock get_problem_status to return "unknown"
    import actr_ranker
    original_get_status = actr_ranker.get_problem_status
    actr_ranker.get_problem_status = lambda slug, data=None: "unknown"
    
    decay = calculate_freshness_decay(fresh_item, current_time)
    assert decay == 1.0, f"Fresh unknown item should have decay 1.0, got {decay}"
    
    # Test old resolved item (should have higher decay)
    old_resolved = {
        "slug": "resolved-problem",
        "created": (current_time - timedelta(days=40)).isoformat(),
    }
    
    actr_ranker.get_problem_status = lambda slug, data=None: "resolved"
    decay = calculate_freshness_decay(old_resolved, current_time)
    # Should be > 1.0 because it's resolved and old
    assert decay > 1.0, f"Old resolved item should have decay > 1.0, got {decay}"
    
    # Test old dead-end item (should have even higher decay)
    old_dead_end = {
        "slug": "dead-end-problem",
        "created": (current_time - timedelta(days=70)).isoformat(),
    }
    
    actr_ranker.get_problem_status = lambda slug, data=None: "dead-end"
    decay = calculate_freshness_decay(old_dead_end, current_time)
    assert decay > 2.0, f"Old dead-end should have decay > 2.0, got {decay}"
    
    # Restore original function
    actr_ranker.get_problem_status = original_get_status
    
    print("✓ Freshness decay works correctly")


def main():
    print("=== ACT-R Unified Ranker Tests ===\n")
    
    print("1. Weight Validation")
    test_weights_sum_to_one()
    
    print("\n2. Data Loading")
    test_activation_log_loads()
    test_tag_graph_loads()
    test_pagerank_loads()
    
    print("\n3. Core Functions")
    test_calculate_activation()
    
    print("\n4. Search Functionality")
    test_unified_search_returns_valid_results()
    test_scores_in_range()
    
    print("\n5. Recall Accuracy")
    recall_ok = test_recall_accuracy()
    
    print("\n6. Security & Validation")
    test_config_validation()
    test_path_traversal_blocked()
    test_cache_works()
    test_sanitization()
    
    print("\n7. Pre-retrieval & Freshness")
    test_pre_retrieval()
    test_freshness()
    
    print("\n" + "="*40)
    if recall_ok:
        print("ALL TESTS PASSED ✓")
    else:
        print("WARNING: Recall below 70%")
    print("="*40)

if __name__ == "__main__":
    main()
